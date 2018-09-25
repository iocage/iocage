# Copyright (c) 2014-2018, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""iocage plugin module"""
import collections
import datetime
import distutils.dir_util
import json
import os
import pathlib
import re
import shutil
import subprocess as su

import requests
from dulwich import porcelain

import iocage_lib.ioc_common
import iocage_lib.ioc_create
import iocage_lib.ioc_destroy
import iocage_lib.ioc_exec
import iocage_lib.ioc_json
import iocage_lib.ioc_upgrade
import libzfs
import texttable
import dulwich.client


class IOCPlugin(object):

    """
    This is responsible for the general life cycle of a plugin jail. This
    includes creation, updating and upgrading.
    """

    def __init__(self, release=None, plugin=None, branch=None,
                 keep_jail_on_failure=False, callback=None, silent=False,
                 **kwargs):
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.release = release
        self.plugin = plugin
        self.http = kwargs.pop("http", True)
        self.server = kwargs.pop("server", "download.freebsd.org")
        self.hardened = kwargs.pop("hardened", False)
        self.date = datetime.datetime.utcnow().strftime("%F")
        self.branch = branch
        self.silent = silent
        self.callback = callback
        self.keep_jail_on_failure = keep_jail_on_failure

        if self.branch is None and not self.hardened:
            freebsd_version = su.run(['freebsd-version'],
                                     stdout=su.PIPE,
                                     stderr=su.STDOUT)
            r = freebsd_version.stdout.decode().rstrip().split('-', 1)[0]

            self.branch = f'{r}-RELEASE' if '.' in r else f'{r}.0-RELEASE'
        elif self.branch is None and self.hardened:
            # Backwards compat
            self.branch = 'master'

    def fetch_plugin(self, _json, props, num, accept_license):
        """Helper to fetch plugins"""

        _json = f"{self.iocroot}/.plugin_index/{_json}.json" if not \
            _json.endswith(".json") else _json

        try:
            with open(f"{self.iocroot}/.plugin_index/INDEX", "r") as plugins:
                plugins = json.load(plugins)
        except FileNotFoundError:
            # Fresh dataset, time to fetch fresh INDEX
            self.fetch_plugin_index(props)

        try:
            with open(_json, "r") as j:
                conf = json.load(j)
        except FileNotFoundError:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{_json} was not found!"
                },
                _callback=self.callback)
        except json.decoder.JSONDecodeError:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Invalid JSON file supplied, please supply a "
                    "correctly formatted JSON file."
                },
                _callback=self.callback)

        if self.hardened:
            conf['release'] = conf['release'].replace("-RELEASE", "-STABLE")
            conf['release'] = re.sub(r"\W\w.", "-", conf['release'])

        self.release = conf['release']
        self.__fetch_plugin_inform__(conf, num, plugins, accept_license)
        props, pkg = self.__fetch_plugin_props__(conf, props, num)
        jail_name = conf["name"].lower()
        location = f"{self.iocroot}/jails/{jail_name}"

        try:
            devfs = conf.get("devfs_ruleset", None)

            if devfs is not None:
                devfs_cmd = ["service", "devfs", "restart"]
                plugin_devfs = devfs[f'plugin_{jail_name}']
                plugin_devfs_paths = plugin_devfs['paths']

                for prop in props:
                    key, _, value = prop.partition("=")

                    if key == "dhcp" and value == "on":
                        if 'bpf*' not in plugin_devfs_paths:
                            plugin_devfs_paths["bpf*"] = None

                plugin_devfs_includes = None if 'includes' not in plugin_devfs\
                    else plugin_devfs['includes']

                with open("/etc/devfs.rules", "a+") as devfs:
                    # Same plugin, so the name being unique as it might become
                    # later does not matter
                    devfs_str, devfs_rule = \
                        iocage_lib.ioc_common.construct_devfs(
                            f'plugin_{jail_name}',
                            paths=plugin_devfs_paths,
                            includes=plugin_devfs_includes
                        )

                    if 'bpf*' in plugin_devfs_paths:
                        # Plugin needs to use it now
                        props += [f'devfs_ruleset={devfs_rule}']

                    if devfs_str is not None:
                        devfs.write(devfs_str)
                        su.check_call(devfs_cmd, stdout=su.PIPE,
                                      stderr=su.PIPE)

            jail_name, jaildir, _conf, repo_dir = self.__fetch_plugin_create__(
                props, jail_name)
            location = f"{self.iocroot}/jails/{jail_name}"
            self.__fetch_plugin_install_packages__(jail_name, jaildir, conf,
                                                   _conf, pkg, props, repo_dir)
            self.__fetch_plugin_post_install__(conf, _conf, jaildir, jail_name)
        except (KeyboardInterrupt, SystemExit, RuntimeError) as e:
            if not self.keep_jail_on_failure:
                iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(location)
                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': f'Exception: {str(e)} occured, destroyed '
                               f'{jail_name}.'
                },
                    _callback=self.callback,
                    silent=self.silent)
            raise

    def __fetch_plugin_inform__(self, conf, num, plugins, accept_license):
        """Logs the pertinent information before fetching a plugin"""

        if num <= 1:
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f"Plugin: {conf['name']}"
                },
                _callback=self.callback,
                silent=self.silent)
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message":
                    f"  Official Plugin: {conf.get('official', False)}"
                },
                _callback=self.callback,
                silent=self.silent)
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f"  Using RELEASE: {conf['release']}"
                },
                _callback=self.callback,
                silent=self.silent)
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f"  Using Branch: {self.branch}"
                },
                _callback=self.callback,
                silent=self.silent)
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f"  Post-install Artifact: {conf['artifact']}"
                },
                _callback=self.callback,
                silent=self.silent)
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "  These pkgs will be installed:"
                },
                _callback=self.callback,
                silent=self.silent)

            for pkg in conf["pkgs"]:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": f"    - {pkg}"
                    },
                    _callback=self.callback,
                    silent=self.silent)

            # Name would be convenient, but it doesn't always gel with the
            # JSON's title, pkg always does.
            try:
                license = plugins[pkg.split("/", 1)[-1]].get("license", False)
            except UnboundLocalError:
                license = plugins.get(
                    conf["name"].lower().split("/", 1)[-1],
                    conf
                ).get("license", False)
            except KeyError:
                # quassel-core is one that does this.
                license = plugins.get(
                    conf["name"].strip("-").lower().split("/", 1)[-1],
                    conf
                ).get("license", False)

            if license and not accept_license:
                license_text = requests.get(license)

                iocage_lib.ioc_common.logit(
                    {
                        "level": "WARNING",
                        "message":
                         "  This plugin requires accepting a license "
                        "to proceed:"
                    },
                    _callback=self.callback,
                    silent=self.silent)
                iocage_lib.ioc_common.logit(
                    {
                        "level": "VERBOSE",
                        "message": f"{license_text.text}"
                    },
                    _callback=self.callback,
                    silent=self.silent)

                agree = input("Do you agree? (y/N) ")

                if agree.lower() != "y":
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message":
                            "You must accept the license to continue!"
                        },
                        _callback=self.callback)

    def __fetch_plugin_props__(self, conf, props, num):
        """Generates the list of properties that a user and the JSON supply"""
        self.release = conf["release"]
        pkg_repos = conf["fingerprints"]
        freebsd_version = f"{self.iocroot}/releases/{conf['release']}" \
            "/root/bin/freebsd-version"
        json_props = conf.get("properties", {})
        props = list(props)

        for p, v in json_props.items():
            # The JSON properties are going to be treated as user entered
            # ones on the command line. If the users prop exists on the
            # command line, we will skip the JSON one.
            _p = f"{p}={v}"

            if p not in [_prop.split("=")[0] for _prop in props]:
                props.append(_p)

            if not os.path.isdir(f"{self.iocroot}/releases/{self.release}"):
                iocage_lib.ioc_common.check_release_newer(
                    self.release, self.callback, self.silent)
                self.__fetch_release__(self.release)

        if conf["release"][:4].endswith("-"):
            # 9.3-RELEASE and under don't actually have this binary.
            release = conf["release"]
        else:
            iocage_lib.ioc_common.check_release_newer(
                self.release, self.callback, self.silent)

            try:
                with open(freebsd_version, "r") as r:
                    for line in r:
                        if line.startswith("USERLAND_VERSION"):
                            release = line.rstrip().partition("=")[2].strip(
                                '"')
            except FileNotFoundError:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "WARNING",
                        "message": f"Release {self.release} missing, "
                        f"will attempt to fetch it."
                    },
                    _callback=self.callback,
                    silent=self.silent)

                self.__fetch_release__(self.release)

                # We still want this.
                with open(freebsd_version, "r") as r:
                    for line in r:
                        if line.startswith("USERLAND_VERSION"):
                            release = line.rstrip().partition("=")[2].strip(
                                '"')

        # We set our properties that we need, and then iterate over the user
        # supplied properties replacing ours.
        create_props = [
            f"cloned_release={self.release}", f"release={release}",
            "type=pluginv2", "boot=on"
        ]

        create_props = [f"{k}={v}" for k, v in (p.split("=")
                                                for p in props)] + create_props

        return create_props, pkg_repos

    def __fetch_plugin_create__(self, create_props, uuid):
        """Creates the plugin with the provided properties"""
        uuid = iocage_lib.ioc_create.IOCCreate(
                self.release,
                create_props,
                0,
                silent=True,
                basejail=True,
                uuid=uuid,
                plugin=True,
                callback=self.callback
        ).create_jail()

        jaildir = f"{self.iocroot}/jails/{uuid}"
        repo_dir = f"{jaildir}/root/usr/local/etc/pkg/repos"
        path = f"{self.pool}/iocage/jails/{uuid}"
        _conf = iocage_lib.ioc_json.IOCJson(jaildir).json_load()

        # We do this test again as the user could supply a malformed IP to
        # fetch that bypasses the more naive check in cli/fetch

        if _conf["ip4_addr"] == "none" and _conf["ip6_addr"] == "none" and \
           _conf["dhcp"] != "on":
            iocage_lib.ioc_common.logit(
                {
                    "level": "ERROR",
                    "message": "\nAn IP address is needed to fetch a "
                    "plugin!\n"
                },
                _callback=self.callback,
                silent=self.silent)
            iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(path)
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Destroyed partial plugin."
                },
                _callback=self.callback)

        return uuid, jaildir, _conf, repo_dir

    def __fetch_plugin_install_packages__(self, uuid, jaildir, conf, _conf,
                                          pkg_repos, create_props, repo_dir):
        """Attempts to start the jail and install the packages"""
        kmods = conf.get("kmods", {})
        secure = True if "https://" in conf["packagesite"] else False

        for kmod in kmods:
            try:
                su.check_call(
                    ["kldload", "-n", kmod], stdout=su.PIPE, stderr=su.PIPE)
            except su.CalledProcessError:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": "Module not found!"
                    },
                    _callback=self.callback)

        if secure:
            # Certificate verification
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "Secure packagesite detected, installing "
                    "ca_root_nss package."
                },
                _callback=self.callback,
                silent=self.silent)

            err = iocage_lib.ioc_create.IOCCreate(
                self.release,
                create_props,
                0,
                pkglist=["ca_root_nss"],
                silent=True,
                callback=self.callback).create_install_packages(
                    uuid, jaildir, _conf)

            if err:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message":
                        "pkg error, please try non-secure packagesite."
                    },
                    _callback=self.callback)

        try:
            os.makedirs(f"{jaildir}/root/usr/local/etc/pkg/repos", 0o755)
        except OSError:
            # Same as below, it exists and we're OK with that.
            pass

        freebsd_conf = """\
FreeBSD: { enabled: no }
"""

        try:
            os.makedirs(repo_dir, 0o755)
        except OSError:
            # It exists, that's fine.
            pass

        with open(f"{jaildir}/root/usr/local/etc/pkg/repos/FreeBSD.conf",
                  "w") as f_conf:
            f_conf.write(freebsd_conf)

        for repo in pkg_repos:
            repo_name = repo
            repo = pkg_repos[repo]
            f_dir = f"{jaildir}/root/usr/local/etc/pkg/fingerprints/" \
                f"{repo_name}/trusted"
            repo_conf = """\
{reponame}: {{
            url: "{packagesite}",
            signature_type: "fingerprints",
            fingerprints: "/usr/local/etc/pkg/fingerprints/{reponame}",
            enabled: true
            }}
"""

            try:
                os.makedirs(f_dir, 0o755)
            except OSError:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "ERROR",
                        "message":
                        f"Repo: {repo_name} already exists, skipping!"
                    },
                    _callback=self.callback,
                    silent=self.silent)

            r_file = f"{repo_dir}/{repo_name}.conf"

            with open(r_file, "w") as r_conf:
                r_conf.write(
                    repo_conf.format(
                        reponame=repo_name, packagesite=conf["packagesite"]))

            f_file = f"{f_dir}/{repo_name}"

            for r in repo:
                finger_conf = """\
function: {function}
fingerprint: {fingerprint}
"""
                with open(f_file, "w") as f_conf:
                    f_conf.write(
                        finger_conf.format(
                            function=r["function"],
                            fingerprint=r["fingerprint"]))

        err = iocage_lib.ioc_create.IOCCreate(
            self.release,
            create_props,
            0,
            pkglist=conf["pkgs"],
            silent=True,
            plugin=True,
            callback=self.callback).create_install_packages(
                uuid, jaildir, _conf, repo=conf["packagesite"], site=repo_name)

        if err:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"\npkg error:\n  - {err}\n"
                    "\nRefusing to fetch artifact and run post_install.sh!"
                },
                _callback=self.callback)

    def __fetch_plugin_post_install__(self, conf, _conf, jaildir, uuid):
        """Fetches the users artifact and runs the post install"""
        dhcp = False

        ip4 = _conf["ip4_addr"]
        if '|' in ip4:
            ip4 = ip4.split("|")[1].rsplit("/")[0]

        ip6 = _conf["ip6_addr"]
        if '|' in ip6:
            ip6 = ip6.split("|")[1].rsplit("/")[0]

        if ip4 != "none":
            ip = ip4
        elif ip6 != "none":
            # If they had an IP4 address and an IP6 one,
            # we'll assume they prefer IP6.
            ip = ip6
        else:
            dhcp = True
            ip = ""

        plugin_env = {"IOCAGE_PLUGIN_IP": ip.rsplit(',')[0]}

        # We need to pipe from tar to the root of the jail.

        if conf["artifact"]:
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "\nFetching artifact... "
                },
                _callback=self.callback,
                silent=self.silent)

            self.__clone_repo(conf['artifact'], f'{jaildir}/plugin')

            with open(f"{jaildir}/{uuid.rsplit('_', 1)[0]}.json", "w") as f:
                f.write(json.dumps(conf, indent=4, sort_keys=True))

            try:
                distutils.dir_util.copy_tree(
                    f"{jaildir}/plugin/overlay/",
                    f"{jaildir}/root",
                    preserve_symlinks=True)
            except distutils.errors.DistutilsFileError:
                # It just doesn't exist
                pass

            try:
                shutil.copy(f"{jaildir}/plugin/post_install.sh",
                            f"{jaildir}/root/root")

                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": "\nRunning post_install.sh"
                    },
                    _callback=self.callback,
                    silent=self.silent)

                command = ["/bin/sh", "/root/post_install.sh"]
                msg, err = iocage_lib.ioc_exec.IOCExec(
                    command, uuid, jaildir, plugin=True,
                    skip=True, callback=self.callback,
                    msg_return=True, su_env=plugin_env).exec_jail()

                if err:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": "An error occured! Please read above"
                        }, _callback=self.callback)

                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": msg.decode()
                    },
                    _callback=self.callback)

                ui_json = f"{jaildir}/plugin/ui.json"

                if dhcp:
                    interface = _conf["interfaces"].split(",")[0].split(":")[0]

                    if interface == "vnet0":
                        # Jails use epairNb by default inside
                        interface = f"{interface.replace('vnet', 'epair')}b"

                    ip4_cmd = [
                        "jexec", f"ioc-{uuid}", "ifconfig", interface, "inet"
                    ]
                    out = su.check_output(ip4_cmd).decode()
                    ip = f"{out.splitlines()[2].split()[1]}"
                    os.environ["IOCAGE_PLUGIN_IP"] = ip

                try:
                    with open(ui_json, "r") as u:
                        admin_portal = json.load(u)["adminportal"]
                        admin_portal = admin_portal.replace("%%IP%%",
                                                            ip.rsplit(',')[0])
                        iocage_lib.ioc_common.logit(
                            {
                                "level": "INFO",
                                "message": f"Admin Portal:\n{admin_portal}"
                            },
                            _callback=self.callback,
                            silent=self.silent)
                except FileNotFoundError:
                    # They just didn't set a admin portal.
                    pass
            except FileNotFoundError:
                pass

    def fetch_plugin_index(self,
                           props,
                           _list=False,
                           list_header=False,
                           list_long=False,
                           accept_license=False,
                           icon=False,
                           official=False):

        if self.server == "download.freebsd.org":
            git_server = "https://github.com/freenas/iocage-ix-plugins.git"
        else:
            git_server = self.server

        git_working_dir = f"{self.iocroot}/.plugin_index"

        # list --plugins won't often be root.

        if os.geteuid() == 0:
            try:
                self.__clone_repo(git_server, git_working_dir)
            except Exception as err:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": err
                    },
                    _callback=self.callback)

        with open(f"{self.iocroot}/.plugin_index/INDEX", "r") as plugins:
            plugins = json.load(plugins)

        _plugins = self.__fetch_sort_plugin__(plugins, official=official)

        if self.plugin is None and not _list:
            for p in _plugins:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": f"[{_plugins.index(p)}] {p}"
                    },
                    _callback=self.callback,
                    silent=self.silent)

        if _list:
            plugin_list = []

            for p in _plugins:
                p = p.split("-", 1)
                name = p[0]
                desc, pkg = re.sub(r'[()]', '', p[1]).rsplit(" ", 1)
                license = plugins[pkg].get("license", "")
                _official = str(plugins[pkg].get("official", False))
                icon_path = plugins[pkg].get("icon", None)

                p = [name, desc, pkg]

                if not list_header:
                    p += [license, _official]

                if icon:
                    p += [icon_path]

                if official and _official == "False":
                    continue

                plugin_list.append(p)

            if not list_header:
                return plugin_list
            else:
                if list_long:
                    table = texttable.Texttable(max_width=0)
                else:
                    table = texttable.Texttable(max_width=80)

                list_header = ["NAME", "DESCRIPTION", "PKG"]

                if icon:
                    list_header += ["ICON"]

                plugin_list.insert(0, list_header)

                table.add_rows(plugin_list)

                return table.draw()

        if self.plugin is None:
            self.plugin = input("\nType the number of the desired"
                                " plugin\nPress [Enter] or type EXIT to"
                                " quit: ")

        self.plugin = self.__fetch_validate_plugin__(self.plugin.lower(),
                                                     _plugins)
        self.fetch_plugin(f"{self.iocroot}/.plugin_index/{self.plugin}.json",
                          props, 0, accept_license)

    def __fetch_validate_plugin__(self, plugin, plugins):
        """
        Checks if the user supplied an index number and returns the
        plugin. If they gave us a plugin name, we make sure that exists in
        the list at all.
        """
        _plugin = plugin  # Gets lost in the enumeration if no match is found.

        if plugin.lower() == "exit":
            exit()

        if len(plugin) <= 2:
            try:
                plugin = plugins[int(plugin)]
            except IndexError:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f"Plugin: {_plugin} not in list!"
                    },
                    _callback=self.callback)
            except ValueError:
                exit()
        else:
            # Quick list validation
            try:
                plugin = [
                    i for i, p in enumerate(plugins)

                    if plugin.capitalize() in p or plugin in p
                ]
                try:
                    plugin = plugins[int(plugin[0])]
                except IndexError:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": f"Plugin: {_plugin} not in list!"
                        },
                        _callback=self.callback)
            except ValueError as err:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": err
                    },
                    _callback=self.callback)

        return plugin.rsplit("(", 1)[1].replace(")", "")

    def __fetch_sort_plugin__(self, plugins, official=False):
        """
        Sort the list by plugin.
        """
        p_dict = {}
        plugin_list = []

        for plugin in plugins:
            _official = str(plugins[plugin].get("official", False))

            if official and _official == "False":
                continue

            _plugin = f"{plugins[plugin]['name']} -" \
                f" {plugins[plugin]['description']}" \
                      f" ({plugin})"
            p_dict[plugin] = _plugin

        ordered_p_dict = collections.OrderedDict(sorted(p_dict.items()))
        index = 0

        for p in ordered_p_dict.values():
            plugin_list.insert(index, f"{p}")
            index += 1

        return plugin_list

    def update(self):
        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Snapshotting {self.plugin}... "
            },
            _callback=self.callback,
            silent=self.silent)

        self.__snapshot_jail__(name="update")

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Updating plugin INDEX... "
            },
            _callback=self.callback,
            silent=self.silent)
        self.__update_pull_plugin_index__()

        plugin_conf = self.__load_plugin_json()
        self.__check_manifest__(plugin_conf)

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Removing old pkgs... "
            },
            _callback=self.callback,
            silent=self.silent)
        self.__update_pkg_remove__()

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Installing new pkgs... "
            },
            _callback=self.callback,
            silent=self.silent)
        self.__update_pkg_install__(plugin_conf)

        if plugin_conf["artifact"]:
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "Updating plugin artifact... "
                },
                _callback=self.callback,
                silent=self.silent)
            self.__update_pull_plugin_artifact__(plugin_conf)

            post_path = \
                f"{self.iocroot}/jails/{self.plugin}/plugin/post_upgrade.sh"

            if os.path.exists(post_path):
                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": "Running post_upgrade.sh... "
                    },
                    _callback=self.callback,
                    silent=self.silent)

                # If the post_upgrade has a service command, we want it to
                # succeed. This is essentially a soft jail restart.
                self.__stop_rc__()
                self.__run_post_upgrade__()
                self.__stop_rc__()
                self.__start_rc__()

        self.__remove_snapshot__(name="update")

    def __update_pull_plugin_index__(self):
        """Pull the latest index to be sure we're up to date"""

        if self.server == "download.freebsd.org":
            git_server = "https://github.com/freenas/iocage-ix-plugins.git"
        else:
            git_server = self.server

        git_working_dir = f"{self.iocroot}/.plugin_index"

        try:
            with open("/dev/null", "wb") as devnull:
                porcelain.pull(git_working_dir, git_server,
                               outstream=devnull, errstream=devnull)
        except Exception as err:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": err
                },
                _callback=self.callback)

    def __update_pull_plugin_artifact__(self, plugin_conf):
        """Pull the latest artifact to be sure we're up to date"""
        path = f"{self.iocroot}/jails/{self.plugin}"

        shutil.rmtree(f"{path}/plugin", ignore_errors=True)
        self.__clone_repo(plugin_conf['artifact'], f'{path}/plugin')

        try:
            distutils.dir_util.copy_tree(
                f"{path}/plugin/overlay/",
                f"{path}/root",
                preserve_symlinks=True)
        except distutils.errors.DistutilsFileError:
            # It just doesn't exist
            pass

    def __update_pkg_remove__(self):
        """Remove all pkgs from the plugin"""
        _, out_stderr, pkg_err = iocage_lib.ioc_exec.IOCExec(
            command=["pkg", "delete", "-a", "-f", "-y"],
            uuid=self.plugin,
            path=f"{self.iocroot}/jails/{self.plugin}",
            silent=True,
            msg_err_return=True,
            callback=self.callback).exec_jail()

        if pkg_err:
            self.__rollback_jail__(name="update")
            msg = out_stderr.decode()
            final_msg = "PKG error, update failed! Rolling back snapshot.\n"

            iocage_lib.ioc_common.logit(
                {
                    "level": "ERROR",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": final_msg
                },
                _callback=self.callback)

    def __update_pkg_install__(self, plugin_conf):
        """Installs all pkgs listed in the plugins configuration"""
        path = f"{self.iocroot}/jails/{self.plugin}"
        conf = iocage_lib.ioc_json.IOCJson(
            location=path).json_load()

        secure = True if "https://" in plugin_conf["packagesite"] else False
        pkg_repos = plugin_conf["fingerprints"]

        if secure:
            # Certificate verification
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "Secure packagesite detected, installing"
                               " ca_root_nss package."
                },
                _callback=self.callback,
                silent=self.silent)

            err = iocage_lib.ioc_create.IOCCreate(
                    self.release,
                    "",
                    0,
                    pkglist=["ca_root_nss"],
                    silent=True, callback=self.callback
                ).create_install_packages(
                    self.plugin,
                    path,
                    conf
                )

            if err:
                self.__rollback_jail__(name="update")
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message":
                        "PKG error, please try non-secure packagesite."
                    },
                    _callback=self.callback)

        for repo in pkg_repos:
            repo_name = repo

            err = iocage_lib.ioc_create.IOCCreate(
                self.release,
                "",
                0,
                pkglist=plugin_conf["pkgs"],
                silent=True,
                plugin=True,
                callback=self.callback).create_install_packages(
                self.plugin,
                path,
                conf,
                repo=plugin_conf["packagesite"],
                site=repo_name)

            if err:
                self.__rollback_jail__(name="update")
                msg = "PKG error, update failed! Rolling back snapshot.\n"
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": msg
                    },
                    _callback=self.callback)

    def upgrade(self):
        jail_conf = iocage_lib.ioc_json.IOCJson(
            location=f"{self.iocroot}/jails/{self.plugin}").json_load()

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Snapshotting {self.plugin}... "
            },
            _callback=self.callback,
            silent=self.silent)

        self.__snapshot_jail__(name="upgrade")

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Updating plugin INDEX... "
            },
            _callback=self.callback,
            silent=self.silent)
        self.__update_pull_plugin_index__()

        plugin_conf = self.__load_plugin_json()
        self.__check_manifest__(plugin_conf)
        plugin_release = plugin_conf["release"]
        iocage_lib.ioc_common.check_release_newer(
            plugin_release, self.callback, self.silent)
        release_p = pathlib.Path(f"{self.iocroot}/releases/{plugin_release}")

        if not release_p.exists():
            iocage_lib.ioc_common.check_release_newer(
                plugin_release, self.callback, self.silent)
            iocage_lib.ioc_common.logit(
                {
                    "level": "WARNING",
                    "message": "New plugin RELEASE missing, fetching now... "
                },
                _callback=self.callback,
                silent=self.silent)
            self.__fetch_release__(plugin_release)

        path = f"{self.iocroot}/jails/{self.plugin}/root"

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Running upgrade... "
            },
            _callback=self.callback,
            silent=self.silent)

        new_release = iocage_lib.ioc_upgrade.IOCUpgrade(
            jail_conf, plugin_release, path, silent=True).upgrade_basejail(
                snapshot=False)

        self.silent = True
        self.update()

        return new_release

    def __snapshot_jail__(self, name):
        """Snapshot the plugin"""
        # Utilize the nicer API interface for this
        import iocage_lib.iocage as ioc  # Avoids dep issues
        name = f"ioc_plugin_{name}_{self.date}"

        ioc.IOCage(
            jail=self.plugin,
            skip_jails=True,
            silent=True
        ).snapshot(name)

    def __rollback_jail__(self, name):
        """Rollback the plugins snapshot"""
        # Utilize the nicer API interface for this
        import iocage_lib.iocage as ioc  # Avoids dep issues
        name = f"ioc_plugin_{name}_{self.date}"

        iocage = ioc.IOCage(
            jail=self.plugin,
            skip_jails=True,
            silent=True)

        iocage.stop()
        iocage.rollback(name)

    def __load_plugin_json(self):
        """Load the plugins configuration"""
        plugin_name = self.plugin.rsplit('_', 1)[0]
        _json = f"{self.iocroot}/.plugin_index/{plugin_name}.json"

        try:
            with open(_json, "r") as j:
                _conf = json.load(j)
        except FileNotFoundError:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{_json} was not found!"
                },
                _callback=self.callback)
        except json.decoder.JSONDecodeError:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message":
                    "Invalid JSON file supplied, please supply a "
                    "correctly formatted JSON file."
                },
                _callback=self.callback)

        return _conf

    def __run_post_upgrade__(self):
        """Run the plugins post_postupgrade.sh"""
        path = f"{self.iocroot}/jails/{self.plugin}"

        shutil.copy(f"{path}/plugin/post_upgrade.sh",
                    f"{path}/root/root")

        command = ["sh", "/root/post_upgrade.sh"]
        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "\nCommand output:"
            },
            _callback=self.callback,
            silent=self.silent)

        out_stdout, err = iocage_lib.ioc_exec.IOCExec(
            command,
            self.plugin,
            path,
            plugin=True,
            skip=True,
            callback=self.callback
        ).exec_jail()

        if err:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "An error occurred! Please read above"
                }, _callback=self.callback)

    def __remove_snapshot__(self, name):
        """Removes all matching plugin snapshots"""
        name = f"ioc_plugin_{name}_{self.date}"
        dataset = self.zfs.get_dataset(
            f"{self.pool}/iocage/jails/{self.plugin}")
        dataset_snaps = dataset.snapshots_recursive

        for snap in dataset_snaps:
            snap_name = snap.snapshot_name

            if snap_name == name:
                snap.delete()

    def __stop_rc__(self):
        iocage_lib.ioc_exec.IOCExec(
            command=["/bin/sh", "/etc/rc.shutdown"],
            uuid=self.plugin,
            path=f"{self.iocroot}/jails/{self.plugin}",
            silent=True,
            msg_err_return=True,
            callback=self.callback
        ).exec_jail()

    def __start_rc__(self):
        iocage_lib.ioc_exec.IOCExec(
            command=["/bin/sh", "/etc/rc"],
            uuid=self.plugin,
            path=f"{self.iocroot}/jails/{self.plugin}",
            silent=True,
            msg_err_return=True,
            callback=self.callback
        ).exec_jail()

    def __check_manifest__(self, plugin_conf):
        """If the Major ABI changed, they cannot update anymore."""
        jail_conf = iocage_lib.ioc_json.IOCJson(
            location=f"{self.iocroot}/jails/{self.plugin}").json_load()

        jail_rel = int(jail_conf["release"].split(".", 1)[0])
        manifest_rel = int(plugin_conf["release"].split(".", 1)[0])
        manifest_major_minor = float(
            plugin_conf["release"].rsplit("-", 1)[0].rsplit("-", 1)[0])

        iocage_lib.ioc_common.check_release_newer(
            manifest_major_minor, self.callback, self.silent)

        if jail_rel < manifest_rel:
            self.__remove_snapshot__(name="update")
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Major ABI change detected, please run"
                    " 'upgrade' instead."
                },
                _callback=self.callback)

    def __fetch_release__(self, release):
        """Will call fetch to get the new RELEASE the plugin will rely on"""
        iocage_lib.ioc_fetch.IOCFetch(
            release, silent=self.silent).fetch_release()

    def __clone_repo(self, repo_url, destination):
        """
        This is to replicate the functionality of cloning/pulling a repo
        """
        try:
            with open('/dev/null', 'wb') as devnull:
                porcelain.pull(destination, repo_url, outstream=devnull,
                               errstream=devnull)
                repo = porcelain.open_repo(destination)
        except dulwich.errors.NotGitRepository:
            with open('/dev/null', 'wb') as devnull:
                repo = porcelain.clone(
                    repo_url, destination, outstream=devnull, errstream=devnull
                )

        remote_refs = porcelain.fetch(repo, repo_url)
        ref = f'refs/heads/{self.branch}'.encode()

        try:
            repo[ref] = remote_refs[ref]
        except KeyError:
            ref = b'refs/heads/master'
            msgs = [
                f'\nBranch {self.branch} does not exist at {repo_url}!',
                'Using "master" branch for plugin, this may not work '
                'with your RELEASE'
            ]

            for msg in msgs:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'INFO',
                        'message': msg
                    },
                    _callback=self.callback)

            repo[ref] = remote_refs[ref]

        tree = repo[ref].tree

        # Let git reflect reality
        repo.reset_index(tree)
        repo.refs.set_symbolic_ref(b'HEAD', ref)
