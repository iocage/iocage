# Copyright (c) 2014-2019, iocage
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
import concurrent.futures
import contextlib
import datetime
import distutils.dir_util
import json
import logging
import os
import git
import pathlib
import re
import shutil
import subprocess as su
import requests
import tarfile
import tempfile
import threading
import urllib.parse
import uuid

import iocage_lib.ioc_common
import iocage_lib.ioc_create
import iocage_lib.ioc_destroy
import iocage_lib.ioc_exec
import iocage_lib.ioc_list
import iocage_lib.ioc_json
import iocage_lib.ioc_start
import iocage_lib.ioc_stop
import iocage_lib.ioc_upgrade
import iocage_lib.ioc_exceptions
import texttable

from iocage_lib.cache import cache
from iocage_lib.dataset import Dataset


GIT_LOCK = threading.Lock()
RE_PLUGIN_VERSION = re.compile(r'"path":"([/\.\+,\d\w-]*)\.txz"')


class IOCPlugin(object):

    """
    This is responsible for the general life cycle of a plugin jail. This
    includes creation, updating and upgrading.
    """

    PLUGIN_VERSION = '2'
    DEFAULT_PROPS = {
        'vnet': 1,
        'boot': 1
    }

    def __init__(
        self, release=None, jail=None, plugin=None, branch=None,
        keep_jail_on_failure=False, callback=None, silent=False, **kwargs
    ):
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.release = release
        if os.path.exists(plugin or ''):
            self.plugin_json_path = plugin
            plugin = plugin.rsplit('/', 1)[-1].rstrip('.json')
            if self.plugin_json_path == jail:
                # If user specified a complete path to plugin json file
                # jail would be having the same value. We ensure that we don't
                # do that here.
                jail = f'{plugin}_{str(uuid.uuid4())[:4]}'
        else:
            self.plugin_json_path = None
        self.plugin = plugin
        self.jail = jail
        self.http = kwargs.pop("http", True)
        self.hardened = kwargs.pop("hardened", False)
        self.date = datetime.datetime.utcnow().strftime("%F")
        self.branch = branch
        self.silent = silent
        self.callback = callback
        self.keep_jail_on_failure = keep_jail_on_failure
        self.thickconfig = kwargs.pop('thickconfig', False)
        self.log = logging.getLogger('iocage')

        # If we have a jail which exists for this plugin, we will like to
        # enforce the plugin to respect the github repository it was
        # created from for updates/upgrades etc. If for some reason, this
        # is not desired, the user is free to change it via "set" manually
        # on his own.
        # TODO: For a lack of ability to do this efficiently/correctly here,
        #  the above should be enforced by the caller of IOCPlugin

        self.git_repository = kwargs.get(
            'git_repository'
        ) or 'https://github.com/freenas/iocage-ix-plugins.git'

        self.git_destination = kwargs.get('git_destination')
        if not self.git_destination:
            # If not provided, we use git repository uri and split on scheme
            # and convert slashes/dot to underscore to guarantee uniqueness
            # i.e github_com_freenas_iocage-ix-plugins_git
            self.git_destination = os.path.join(
                self.iocroot, '.plugins', self.git_repository.split(
                    '://', 1)[-1].replace('/', '_').replace('.', '_')
            )

        if self.branch is None and not self.hardened:
            r = cache.freebsd_version

            self.branch = f'{r}-RELEASE' if '.' in r else f'{r}.0-RELEASE'
        elif self.branch is None and self.hardened:
            # Backwards compat
            self.branch = 'master'

    def pull_clone_git_repo(self, depth=None):
        self._clone_repo(
            self.branch, self.git_repository, self.git_destination,
            depth, self.callback
        )

    @staticmethod
    def fetch_plugin_packagesites(package_sites):
        def download_parse_packagesite(packagesite_url):
            package_site_data = {}

            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    packagesite_txz_path = os.path.join(tmpdir, 'packagesite.txz')
                    with requests.get(
                        f'{packagesite_url}/packagesite.txz', stream=True, timeout=300
                    ) as r:
                        r.raise_for_status()
                        with open(packagesite_txz_path, 'wb') as f:
                            shutil.copyfileobj(r.raw, f)

                    with tarfile.open(packagesite_txz_path) as p_file:
                        p_file.extractall(path=tmpdir)

                    packagesite_path = os.path.join(tmpdir, 'packagesite.yaml')
                    if not os.path.exists(packagesite_path):
                        raise FileNotFoundError(f'{packagesite_path} not found')

                    with open(packagesite_path, 'r') as f:
                        for line in f.read().split('\n'):
                            searched = RE_PLUGIN_VERSION.findall(line)
                            if not searched:
                                continue
                            name = searched[0].rsplit('/', 1)[-1]
                            package_site_data[
                                name.rsplit('-', 1)[0]
                            ] = iocage_lib.ioc_common.parse_package_name(name)
            except Exception:
                pass

            return packagesite_url, package_site_data

        plugin_packagesite_mapping = {}
        package_sites = set([
            url.rstrip('/') for url in package_sites
        ])

        with concurrent.futures.ThreadPoolExecutor() as exc:
            results = exc.map(
                download_parse_packagesite, package_sites
            )

            for result in results:
                plugin_packagesite_mapping[result[0]] = result[1]

        return plugin_packagesite_mapping

    @staticmethod
    def fetch_plugin_versions_from_plugin_index(plugins_index):
        plugin_packagesite_mapping = IOCPlugin.fetch_plugin_packagesites([
            v['packagesite'] for v in plugins_index.values()
        ])

        version_dict = {}
        for plugin in plugins_index:
            plugin_dict = plugins_index[plugin]
            packagesite = plugin_dict['packagesite']
            primary_package = plugin_dict.get('primary_pkg') or plugin
            packagesite = packagesite.rstrip('/')
            plugin_pkgs = plugin_packagesite_mapping[packagesite]
            try:
                version_data = plugin_pkgs[primary_package]
            except KeyError:
                plugin_dict.update({
                    k: 'N/A' for k in ('revision', 'version', 'epoch')
                })
            else:
                plugin_dict.update(version_data)

            version_dict[plugin] = plugin_dict

        return version_dict

    @staticmethod
    def retrieve_plugin_index_data(plugin_index_path, expand_abi=True):
        plugin_index = {}
        index_path = os.path.join(plugin_index_path, 'INDEX')
        if not os.path.exists(index_path):
            return plugin_index

        with open(index_path, 'r') as f:
            index = json.loads(f.read())

        for plugin in index:
            plugin_manifest_path = os.path.join(
                plugin_index_path, index[plugin]['MANIFEST']
            )
            if not os.path.exists(plugin_manifest_path):
                continue

            with open(plugin_manifest_path, 'r') as f:
                plugin_manifest_data = json.loads(f.read())

            if not any(plugin_manifest_data.get(k) for k in ('release', 'packagesite')):
                continue

            if expand_abi and '${ABI}' in plugin_manifest_data['packagesite']:
                plugin_manifest_data['packagesite'] = IOCPlugin.expand_abi_with_specified_release(
                    plugin_manifest_data['packagesite'], plugin_manifest_data['release']
                )

            plugin_index[plugin] = {
                'primary_pkg': index[plugin].get('primary_pkg'),
                'category': index[plugin].get('category'),
                **plugin_manifest_data
            }

        return plugin_index

    @staticmethod
    def expand_abi_with_specified_release(packagesite, release):
        return packagesite.replace(
            '${ABI}', f'FreeBSD:{release.split("-")[0].split(".")[0]}:amd64'
        )

    def fetch_plugin_versions(self):
        self.pull_clone_git_repo()

        plugin_index = self.retrieve_plugin_index_data(self.git_destination)

        return self.fetch_plugin_versions_from_plugin_index(plugin_index)

    def retrieve_plugin_json(self):
        if not self.plugin_json_path:
            _json = os.path.join(self.git_destination, f'{self.plugin}.json')
            if not os.path.exists(self.git_destination):
                self.pull_clone_git_repo()
        else:
            _json = self.plugin_json_path

        self.log.debug(f'Plugin json file path: {_json}')

        try:
            with open(_json, 'r') as j:
                conf = json.load(j)
        except FileNotFoundError:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{_json} was not found!'
                },
                _callback=self.callback
            )
        except json.decoder.JSONDecodeError:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': 'Invalid JSON file supplied, please supply a '
                    'correctly formatted JSON file.'
                },
                _callback=self.callback
            )
        return conf

    def fetch_plugin(self, props, num, accept_license):
        """Helper to fetch plugins"""
        plugins = self.fetch_plugin_index(props, index_only=True)
        conf = self.retrieve_plugin_json()
        iocage_lib.ioc_common.validate_plugin_manifest(conf, self.callback, self.silent)

        if self.hardened:
            conf['release'] = conf['release'].replace("-RELEASE", "-STABLE")
            conf['release'] = re.sub(r"\W\w.", "-", conf['release'])

        self.release = conf['release']
        props, pkg = self.__fetch_plugin_props__(conf, props, num)
        self.__fetch_plugin_inform__(conf, num, plugins, accept_license)
        location = f"{self.iocroot}/jails/{self.jail}"

        try:
            jaildir, _conf, repo_dir = self.__fetch_plugin_create__(props)
            # As soon as we create the jail, we should write the plugin manifest to jail directory
            # This is done to ensure that subsequent starts of the jail make use of the plugin
            # manifest as required
            status, jid = iocage_lib.ioc_list.IOCList().list_get_jid(self.jail)
            if status:
                iocage_lib.ioc_stop.IOCStop(
                    self.jail, jaildir, silent=True, force=True, callback=self.callback
                )
            with open(os.path.join(jaildir, f'{self.plugin}.json'), 'w') as f:
                f.write(json.dumps(conf, indent=4, sort_keys=True))

            self.__fetch_plugin_install_packages__(
                jaildir, conf, pkg, props, repo_dir
            )
            self.__fetch_plugin_post_install__(conf, _conf, jaildir)
        except BaseException as e:
            if not self.keep_jail_on_failure:
                msg = f'{self.jail} had a failure\n' \
                      f'Exception: {e.__class__.__name__} ' \
                      f'Message: {str(e)}\n' \
                      f'Partial plugin destroyed'
                iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(location)
                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': msg
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
        truthy_inverse = iocage_lib.ioc_common.truthy_inverse_values()
        props = {p.split('=')[0]: p.split('=')[1] for p in list(props)}
        network_props = {
            'nat': truthy_inverse, 'dhcp': truthy_inverse,
            'ip4_addr': ('none',), 'ip6_addr=': ('none',)
        }

        for p, v in json_props.items():
            # The JSON properties are going to be treated as user entered
            # ones on the command line. If the users prop exists on the
            # command line, we will skip the JSON one.
            if p not in props:
                if p in network_props and v not in network_props[p]:
                    # This means that "p" is enabled in the plugin manifest
                    # We should now ensure that we don't have any other
                    # connectivity option enabled
                    network_props.pop(p)
                    if any(
                        nk in props and props[nk] not in nv
                        for nk, nv in network_props.items()
                    ):
                        # This means that some other network option has
                        # been specified which is enabled and we don't want
                        # to add the plugin manifest default
                        continue

                props[p] = v

            if not os.path.isdir(f"{self.iocroot}/releases/{self.release}"):
                iocage_lib.ioc_common.check_release_newer(
                    self.release, self.callback, self.silent, major_only=True)
                self.__fetch_release__(self.release)

        if conf["release"][:4].endswith("-"):
            # 9.3-RELEASE and under don't actually have this binary.
            release = conf["release"]
        else:
            iocage_lib.ioc_common.check_release_newer(
                self.release, self.callback, self.silent, major_only=True)

            try:
                with open(
                    freebsd_version, mode='r', encoding='utf-8'
                ) as r:
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
                with open(
                    freebsd_version, mode='r', encoding='utf-8'
                ) as r:
                    for line in r:
                        if line.startswith("USERLAND_VERSION"):
                            release = line.rstrip().partition("=")[2].strip(
                                '"')

        # We set our properties that we need, and then iterate over the user
        # supplied properties replacing ours.
        create_props = [f'release={release}'] + [
            f'{k}={v}' for k, v in {**self.DEFAULT_PROPS, **props}.items()
        ]

        if all(
            props.get(k, 'none') == 'none'
            for k in ('ip4_addr', 'ip6_addr')
        ) and not iocage_lib.ioc_common.boolean_prop_exists(
            create_props, ['dhcp', 'nat', 'ip_hostname']
        ):
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': 'Network connectivity is required to fetch a '
                               'plugin. Please enable dhcp/nat or supply'
                               ' a valid ip address.'
                },
                _callback=self.callback,
                silent=self.silent)

        # These properties are not user configurable

        for prop in (
            f'type=pluginv{self.PLUGIN_VERSION}',
            f'plugin_name={self.plugin}',
            f'plugin_repository={self.git_repository}',
        ):
            create_props.append(prop)

        return create_props, pkg_repos

    def __fetch_plugin_create__(self, create_props):
        """Creates the plugin with the provided properties"""
        iocage_lib.ioc_create.IOCCreate(
            self.release,
            create_props,
            0,
            silent=True,
            basejail=True,
            uuid=self.jail,
            plugin=True,
            thickconfig=self.thickconfig,
            callback=self.callback
        ).create_jail()

        jaildir = f"{self.iocroot}/jails/{self.jail}"
        repo_dir = f"{jaildir}/root/usr/local/etc/pkg/repos"
        path = f"{self.pool}/iocage/jails/{self.jail}"
        _conf = iocage_lib.ioc_json.IOCJson(jaildir).json_get_value('all')

        # We do these tests again as the user could supply a malformed IP to
        # fetch that bypasses the more naive check in cli/fetch
        auto_configs = _conf['dhcp'] or _conf['ip_hostname'] or _conf['nat']

        if _conf["ip4_addr"] == "none" and _conf["ip6_addr"] == "none" and \
           not auto_configs:
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

        return jaildir, _conf, repo_dir

    def __fetch_plugin_install_packages__(self, jaildir, conf, pkg_repos,
                                          create_props, repo_dir):
        """Attempts to start the jail and install the packages"""
        kmods = conf.get("kmods", {})
        secure = True if "https://" in conf["packagesite"] else False

        for kmod in kmods:
            self.log.debug(f'Loading {kmod}')
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
                callback=self.callback
            ).create_install_packages(
                self.jail, jaildir
            )

            if err:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message":
                        "pkg error, please try non-secure packagesite."
                    },
                    _callback=self.callback)

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
            r_dir = f"{jaildir}/root/usr/local/etc/pkg/fingerprints/" \
                f"{repo_name}/revoked"
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
                os.makedirs(r_dir, 0o755)
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
            callback=self.callback
        ).create_install_packages(
            self.jail, jaildir, repo=conf["packagesite"]
        )

        if err:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"\npkg error:\n  - {err}\n"
                    "\nRefusing to fetch artifact and run post_install.sh!"
                },
                _callback=self.callback)

    def __fetch_plugin_post_install__(self, conf, _conf, jaildir):
        """Fetches the users artifact and runs the post install"""
        status, jid = iocage_lib.ioc_list.IOCList().list_get_jid(self.jail)
        if not status:
            iocage_lib.ioc_start.IOCStart(self.jail, jaildir, silent=True)

        ip4 = _conf['ip4_addr']
        ip6 = _conf['ip6_addr']
        ip = None
        if ip6 != 'none':
            ip = ','.join([
                v.split('|')[-1].split('/')[0] for v in ip6.split(',')
                if 'accept_rtadv' not in v.lower()
            ])

        if not ip and ip4 != 'none':
            ip = ','.join([
                v.split('|')[-1].split('/')[0] for v in ip4.split(',')
                if 'dhcp' not in v.lower()
            ])

        if not ip:
            if _conf['vnet']:
                interface = _conf['interfaces'].split(',')[0].split(':')[0]

                if interface == 'vnet0':
                    # Jails use epairNb by default inside
                    interface = f'{interface.replace("vnet", "epair")}b'

                ip4_cmd = [
                    'jexec', f'ioc-{self.jail.replace(".", "_")}',
                    'ifconfig', interface, 'inet'
                ]
                out = su.check_output(ip4_cmd).decode()
                ip = f'{out.splitlines()[2].split()[1]}'
            else:
                ip = json.loads(
                    su.run([
                        'jls', '-j', f'ioc-{self.jail.replace(".", "_")}',
                        '--libxo', 'json'
                    ], stdout=su.PIPE).stdout
                )['jail-information']['jail'][0]['ipv4']

        self.log.debug(f'IP for {self.plugin} - {self.jail}: {ip}.')

        os.environ['IOCAGE_PLUGIN_IP'] = ip

        plugin_env = {
            **{
                k: os.environ.get(k)
                for k in ['http_proxy', 'https_proxy'] if os.environ.get(k)
            },
            'IOCAGE_PLUGIN_IP': ip
        }

        # We need to pipe from tar to the root of the jail.

        if conf["artifact"]:
            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "\nFetching artifact... "
                },
                _callback=self.callback,
                silent=self.silent)

            self.__update_pull_plugin_artifact__(conf)

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

                command = ["/root/post_install.sh"]
                try:
                    with iocage_lib.ioc_exec.IOCExec(
                        command, jaildir, uuid=self.jail, plugin=True,
                        skip=True, callback=self.callback,
                        su_env=plugin_env
                    ) as _exec:
                        iocage_lib.ioc_common.consume_and_log(
                            _exec,
                            callback=self.callback
                        )
                except iocage_lib.ioc_exceptions.CommandFailed as e:
                    message = b' '.join(e.message[-10:]).decode().rstrip()
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': f'Last 10 lines:\n{message}'
                        }, _callback=self.callback)

                ui_json = f"{jaildir}/plugin/ui.json"

                try:
                    with open(ui_json, "r") as u:
                        ui_data = json.load(u)
                        admin_portal = ui_data.get('adminportal', None)
                        doc_url = ui_data.get('docurl', None)

                        if admin_portal:
                            admin_portal = ','.join(
                                iocage_lib.ioc_common.retrieve_admin_portals(
                                    _conf, True, admin_portal
                                )
                            )

                            try:
                                ph = ui_data[
                                    'adminportal_placeholders'
                                ].items()
                                for placeholder, prop in ph:
                                    admin_portal = admin_portal.replace(
                                        placeholder,
                                        iocage_lib.ioc_json.IOCJson(
                                            jaildir).json_plugin_get_value(
                                            prop.split('.'))
                                    )
                            except KeyError:
                                pass

                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'INFO',
                                    'message': '\nAdmin Portal:\n'
                                               f'{admin_portal}'
                                },
                                _callback=self.callback,
                                silent=self.silent)

                        if doc_url is not None:
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'INFO',
                                    'message': f'\nDoc URL:\n{doc_url}'
                                },
                                _callback=self.callback,
                                silent=self.silent)
                except FileNotFoundError:
                    # They just didn't set a admin portal or doc url.
                    pass
            except FileNotFoundError:
                pass

    def fetch_plugin_index(
        self, props, _list=False, list_header=False, list_long=False,
        accept_license=False, icon=False, official=False, index_only=False
    ):
        self.pull_clone_git_repo()

        index_path = os.path.join(self.git_destination, 'INDEX')
        if not os.path.exists(index_path):
            # Gracefully handle index not existing bit
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': 'Unable to retrieve INDEX of '
                               f'{self.git_destination} at '
                               f'{index_path}.'
                },
                _callback=self.callback,
                silent=self.silent
            )
        else:
            with open(index_path, 'r') as plugins:
                plugins = json.load(plugins)

        if index_only:
            return plugins

        plugins_ordered_dict = collections.OrderedDict(
            sorted({
                k: {'name': v['name'], 'description': v['description']}
                for k, v in plugins.items()
                if not (official and not v.get('official', False))
            }.items())
        )

        if self.plugin is None and not _list:
            for i, p in enumerate(plugins_ordered_dict.items()):
                k, v = p
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'INFO',
                        'message':
                            f'[{i}] {v["name"]} - {v["description"]} ({k})'
                    },
                    _callback=self.callback,
                    silent=self.silent
                )

        if _list:
            plugin_list = []

            for k, v in plugins_ordered_dict.items():
                plugin_dict = {
                    'name': v['name'],
                    'description': v['description'],
                    'plugin': k,
                }

                if not list_header:
                    plugin_dict.update({
                        'license': plugins[k].get('license', ''),
                        'official': plugins[k].get('official', False),
                        'category': plugins[k].get('category', None),
                    })

                if icon:
                    plugin_dict['icon'] = plugins[k].get('icon', None)

                plugin_list.append(plugin_dict)

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

                plugin_list = [
                    [p['name'], p['description'], p['plugin']] + (
                        [p['icon']] if icon else []
                    )
                    for p in plugin_list
                ]
                plugin_list.insert(0, list_header)

                table.add_rows(plugin_list)

                return table.draw()

        if self.plugin is None:
            self.plugin = input("\nType the number of the desired"
                                " plugin\nPress [Enter] or type EXIT to"
                                " quit: ")

        self.plugin = self.__fetch_validate_plugin__(
            self.plugin.lower(), plugins_ordered_dict
        )
        self.jail = f'{self.plugin}_{str(uuid.uuid4())[:4]}'

        # We now run the fetch the user requested
        self.fetch_plugin(props, 0, accept_license)

    def __fetch_validate_plugin__(self, plugin, plugins):
        """
        Checks if the user supplied an index number and returns the
        plugin. If they gave us a plugin name, we make sure that exists in
        the list at all.
        """
        _plugin = plugin  # Gets lost in the enumeration if no match is found.

        if plugin.lower() == "exit":
            exit()

        if plugin.isdigit():
            try:
                plugin = list(plugins.items())[int(plugin)][0]
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
            if plugin not in plugins:
                for k, v in plugins.items():
                    if plugin == v['name']:
                        plugin = k
                        break
                else:
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': f'Plugin: {_plugin} not available.'
                        },
                        _callback=self.callback
                    )

        return plugin

    def __run_hook_script__(self, script_path):
        # If the hook script has a service command, we want it to
        # succeed. This is essentially a soft jail restart.
        self.stop_rc()
        path = f"{self.iocroot}/jails/{self.jail}"

        jail_path = os.path.join(self.iocroot, 'jails', self.jail)
        new_script_path = os.path.join(jail_path, 'root/tmp')

        shutil.copy(script_path, new_script_path)
        script_path = os.path.join(
            new_script_path, script_path.split('/')[-1]
        )

        try:
            with iocage_lib.ioc_exec.IOCExec(
                ['sh', os.path.join('/tmp', script_path.split('/')[-1])],
                path,
                uuid=self.jail,
                plugin=True,
                skip=True,
                callback=self.callback
            ) as _exec:
                iocage_lib.ioc_common.consume_and_log(
                    _exec,
                    callback=self.callback,
                    log=not self.silent
                )
        except iocage_lib.ioc_exceptions.CommandFailed as e:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': b'\n'.join(e.message).decode()
                },
                _callback=self.callback,
                silent=self.silent
            )
        else:
            self.stop_rc()
            self.start_rc()

    def update(self, jid):
        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Snapshotting {self.jail}... "
            },
            _callback=self.callback,
            silent=self.silent)

        try:
            self.__snapshot_jail__(name='update')
        except iocage_lib.ioc_exceptions.Exists:
            # User may have run update already (so clean) or they created this
            # snapshot purposely, this is OK
            pass

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Updating plugin INDEX... "
            },
            _callback=self.callback,
            silent=self.silent)
        self.pull_clone_git_repo()

        plugin_conf = self._load_plugin_json()
        self.__check_manifest__(plugin_conf, upgrade=False)

        if plugin_conf['artifact']:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'INFO',
                    'message': 'Updating plugin artifact... '
                },
                _callback=self.callback,
                silent=self.silent
            )
            self.__update_pull_plugin_artifact__(plugin_conf)
            pre_update_hook = os.path.join(
                self.iocroot, 'jails', self.jail, 'plugin/pre_update.sh'
            )
            if os.path.exists(pre_update_hook):
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'INFO',
                        'message': 'Running pre_update.sh... '
                    },
                    _callback=self.callback,
                    silent=self.silent
                )
                self.__run_hook_script__(pre_update_hook)

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Removing old pkgs... "
            },
            _callback=self.callback,
            silent=self.silent)
        self.__update_pkg_remove__(jid)

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Installing new pkgs... "
            },
            _callback=self.callback,
            silent=self.silent)
        self.__update_pkg_install__(plugin_conf)

        if plugin_conf["artifact"]:
            # We need to do this again to ensure that if some files
            # were removed when we removed pkgs and the overlay directory
            # is supposed to bring them back, this does that
            self.__update_pull_plugin_artifact__(plugin_conf)
            post_update_hook = os.path.join(
                self.iocroot, 'jails', self.jail, 'plugin/post_update.sh'
            )
            if os.path.exists(post_update_hook):
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'INFO',
                        'message': 'Running post_update.sh... '
                    },
                    _callback=self.callback,
                    silent=self.silent
                )
                self.__run_hook_script__(post_update_hook)

        self.__remove_snapshot__(name="update")

    def __update_pull_plugin_artifact__(self, plugin_conf):
        """Pull the latest artifact to be sure we're up to date"""
        path = f"{self.iocroot}/jails/{self.jail}"

        shutil.rmtree(f"{path}/plugin", ignore_errors=True)

        uri = urllib.parse.urlparse(plugin_conf['artifact'])
        if uri.scheme == 'file':
            artifact_path = urllib.parse.unquote(uri.path)
            if not os.path.exists(artifact_path):
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': f'{artifact_path} does not exist!'
                    },
                    _callback=self.callback,
                    silent=self.silent
                )

            distutils.dir_util.copy_tree(
                artifact_path,
                os.path.join(path, 'plugin')
            )
        else:
            self._clone_repo(
                plugin_conf['release'], plugin_conf['artifact'],
                f'{path}/plugin', callback=self.callback
            )

        if os.path.isdir(f"{path}/plugin/overlay/"):
            try:
                # Quickfix for distutils cache bug making re-installed
                # plugins with same name fail to copy the overlay folder
                distutils.dir_util._path_created = {}

                distutils.dir_util.copy_tree(
                    f"{path}/plugin/overlay/",
                    f"{path}/root",
                    preserve_symlinks=True)
            except distutils.errors.DistutilsFileError as e:
                # Copy tree should succeed if the overlay folder exists
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': f'Error during overlay copy: {str(e)}'
                    },
                    _callback=self.callback,
                    silent=self.silent
                )

    def __update_pkg_remove__(self, jid):
        """Remove all pkgs from the plugin"""
        try:
            with iocage_lib.ioc_exec.IOCExec(
                command=['pkg', '-j', jid, 'delete', '-a', '-f', '-y'],
                path=f'{self.iocroot}/jails/{self.jail}',
                uuid=self.jail,
                callback=self.callback,
                unjailed=True
            ) as _exec:
                iocage_lib.ioc_common.consume_and_log(
                    _exec,
                    callback=self.callback,
                    log=not(self.silent)
                )
        except iocage_lib.ioc_exceptions.CommandFailed as e:
            self.__rollback_jail__(name="update")
            final_msg = "PKG error, update failed! Rolling back snapshot.\n"

            iocage_lib.ioc_common.logit(
                {
                    "level": "ERROR",
                    "message": b'\n'.join(e.message).decode()
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
        path = f"{self.iocroot}/jails/{self.jail}"

        try:
            self.__fetch_plugin_install_packages__(
                path, plugin_conf, plugin_conf['fingerprints'], [],
                os.path.join(path, 'root/usr/local/etc/pkg/repos')
            )
        except (Exception, SystemExit):
            iocage_lib.ioc_common.logit(
                {
                    'level': 'ERROR',
                    'message': 'PKG error, update failed! '
                               'Rolling back snapshot.\n'
                },
                _callback=self.callback
            )
            self.__rollback_jail__(name='update')
            raise

    def upgrade(self, jid):
        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Snapshotting {self.jail}... "
            },
            _callback=self.callback,
            silent=self.silent)

        try:
            self.__snapshot_jail__(name='upgrade')
        except iocage_lib.ioc_exceptions.Exists:
            # User may have run upgrade already (so clean) or they created this
            # snapshot purposely, this is OK
            pass

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Updating plugin INDEX... "
            },
            _callback=self.callback,
            silent=self.silent)
        self.pull_clone_git_repo()

        plugin_conf = self._load_plugin_json()
        self.__check_manifest__(plugin_conf, upgrade=True)
        plugin_release = plugin_conf["release"]
        iocage_lib.ioc_common.check_release_newer(
            plugin_release, self.callback, self.silent, major_only=True)

        # We want the new json to live with the jail
        plugin_name = self.plugin.rsplit('_', 1)[0]
        shutil.copy(
            os.path.join(self.git_destination, f'{plugin_name}.json'),
            os.path.join(
                self.iocroot, 'jails', self.jail, f'{plugin_name}.json'
            )
        )

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

        path = f"{self.iocroot}/jails/{self.jail}/root"

        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": "Running upgrade... "
            },
            _callback=self.callback,
            silent=self.silent)

        new_release = iocage_lib.ioc_upgrade.IOCUpgrade(
            plugin_release, path, silent=True
        ).upgrade_basejail(
            snapshot=False, snap_name=f'ioc_plugin_upgrade_{self.date}'
        )

        self.update(jid)

        return new_release

    def __snapshot_jail__(self, name):
        """Snapshot the plugin"""
        # Utilize the nicer API interface for this
        import iocage_lib.iocage as ioc  # Avoids dep issues
        name = f"ioc_plugin_{name}_{self.date}"

        ioc.IOCage(
            jail=self.jail,
            skip_jails=True,
            silent=True
        ).snapshot(name)

    def __rollback_jail__(self, name):
        """Rollback the plugins snapshot"""
        # Utilize the nicer API interface for this
        import iocage_lib.iocage as ioc  # Avoids dep issues
        name = f"ioc_plugin_{name}_{self.date}"

        iocage = ioc.IOCage(
            jail=self.jail,
            skip_jails=True,
            silent=True)

        iocage.stop()
        iocage.rollback(name)

    def _plugin_json_file(self):
        plugin_name = self.plugin.rsplit('_', 1)[0]
        jail_name = self.jail or plugin_name
        try:
            with open(
                os.path.join(
                    self.iocroot, 'jails', jail_name, f'{plugin_name}.json'
                ), 'r'
            ) as f:
                manifest = json.loads(f.read())
        except Exception:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'Failed retrieving {jail_name} json'
                },
                _callback=self.callback
            )
        else:
            return manifest

    def _load_plugin_json(self):
        """Load the plugins configuration"""
        plugin_name = self.plugin.rsplit('_', 1)[0]
        _json = os.path.join(self.git_destination, f'{plugin_name}.json')

        try:
            with open(_json, "r") as j:
                _conf = json.load(j)
        except FileNotFoundError:
            _conf = self.__find_plugin_json(plugin_name)
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

    def __find_plugin_json(self, plugin_name):
        """Matches the name of the local plugin's json with the INDEX's"""
        _json = f'{self.iocroot}/jails/{self.plugin}/{plugin_name}.json'

        try:
            with open(_json, 'r') as j:
                p_conf = json.load(j)
                p_name = p_conf['name']
        except FileNotFoundError:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{_json} was not found!'
                },
                _callback=self.callback)
        except json.decoder.JSONDecodeError:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message':
                    'Invalid JSON file supplied, please supply a '
                    'correctly formatted JSON file.'
                },
                _callback=self.callback)

        jsons = pathlib.Path(self.git_destination).glob('*.json')

        for f in jsons:
            _conf = json.loads(pathlib.Path(f).open('r').read())

            if _conf['name'] == p_name:
                return _conf

        iocage_lib.ioc_common.logit(
            {
                'level': 'EXCEPTION',
                'message': f'A plugin manifest matching {p_name} could not '
                           'be found!'
            },
            _callback=self.callback)

    def __remove_snapshot__(self, name):
        """Removes all matching plugin snapshots"""
        conf = iocage_lib.ioc_json.IOCJson(
            f'{self.iocroot}/jails/{self.jail}'
        ).json_get_value('all')
        release = conf['release']
        names = [f'ioc_plugin_{name}_{self.date}', f'ioc_update_{release}']

        for snap in Dataset(
            f'{self.pool}/iocage/jails/{self.jail}'
        ).snapshots_recursive():
            snap_name = snap.name

            if snap_name in names:
                snap.destroy(recursive=False, force=False)

    def stop_rc(self):
        iocage_lib.ioc_exec.SilentExec(
            command=["/bin/sh", "/etc/rc.shutdown"],
            path=f"{self.iocroot}/jails/{self.jail}",
            uuid=self.jail,
            callback=self.callback
        )

    def start_rc(self):
        iocage_lib.ioc_exec.SilentExec(
            command=["/bin/sh", "/etc/rc"],
            path=f"{self.iocroot}/jails/{self.jail}",
            uuid=self.jail,
            callback=self.callback
        )

    def __check_manifest__(self, plugin_conf, upgrade):
        """If the Major ABI changed, they cannot update anymore."""
        jail_conf, write = iocage_lib.ioc_json.IOCJson(
            location=f"{self.iocroot}/jails/{self.jail}").json_load()

        jail_rel = int(jail_conf["release"].split(".", 1)[0])
        manifest_rel = int(plugin_conf["release"].split(".", 1)[0])
        manifest_major_minor = float(
            plugin_conf["release"].rsplit("-", 1)[0].rsplit("-", 1)[0])

        iocage_lib.ioc_common.check_release_newer(
            manifest_major_minor, self.callback, self.silent)

        if not upgrade and jail_rel < manifest_rel:
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
        fetch_args = {'release': release, 'eol': False}
        iocage_lib.iocage.IOCage(silent=self.silent).fetch(**fetch_args)

    @staticmethod
    def _verify_git_repo(repo_url, destination):
        verified = False
        with contextlib.suppress(
            git.exc.InvalidGitRepositoryError,
            git.exc.NoSuchPathError,
            AttributeError,
        ):
            repo = git.Repo(destination)
            verified = any(u == repo_url for u in repo.remotes.origin.urls)

        return verified

    @staticmethod
    def _clone_repo(ref, repo_url, destination, depth=None, callback=None):
        """
        This is to replicate the functionality of cloning/pulling a repo
        """
        with GIT_LOCK:
            branch = ref
            try:
                if os.path.exists(
                    destination
                ) and not IOCPlugin._verify_git_repo(repo_url, destination):
                    raise git.exc.InvalidGitRepositoryError()

                # "Pull"
                repo = git.Repo(destination)
                origin = repo.remotes.origin
                ref = 'master' if f'origin/{ref}' not in repo.refs else ref
                for command in [
                    ['checkout', ref],
                    ['pull']
                ]:
                    iocage_lib.ioc_exec.SilentExec(
                        ['git', '-C', destination] + command,
                        None, unjailed=True, decode=True,
                        su_env={
                            k: os.environ.get(k)
                            for k in ['http_proxy', 'https_proxy'] if
                            os.environ.get(k)
                        }
                    )
            except (
                iocage_lib.ioc_exceptions.CommandFailed,
                git.exc.InvalidGitRepositoryError,
                git.exc.NoSuchPathError
            ) as e:

                basic_msg = 'Failed to update git repository:'
                exception_message = ''

                if isinstance(e, git.exc.NoSuchPathError):
                    f_msg = 'Cloning git repository'
                elif isinstance(e, git.exc.InvalidGitRepositoryError):
                    f_msg = f'{basic_msg} Invalid Git Repository'
                else:
                    exception_message = b' '.join(
                        filter(bool, e.message)
                    ).decode()
                    f_msg = f'{basic_msg} ' \
                        f'{exception_message}'

                iocage_lib.ioc_common.logit(
                    {
                        'level': 'ERROR',
                        'message': f_msg
                    }
                )

                if exception_message.strip().startswith(
                    'fatal: unable to access'
                ):
                    # It is possible the user had a bad network and we
                    # would be in this case destroying the plugin repository
                    # which would function okay to at least get the
                    # required data points while listing plugins
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'ERROR',
                            'message': f'Not cloning {repo_url}'
                                       'as git-pull failed due to '
                                       'network issues.'
                        }
                    )
                    return

                # Clone
                shutil.rmtree(destination, ignore_errors=True)
                kwargs = {'env': os.environ.copy(), 'depth': depth}
                repo = git.Repo.clone_from(
                    repo_url, destination, **{
                        k: v for k, v in kwargs.items() if v
                    }
                )
                origin = repo.remotes.origin

            if not origin.exists():
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': f'Origin: {origin.url} does not exist!'
                    },
                    _callback=callback
                )

            if f'origin/{ref}' not in repo.refs:
                ref = 'master'
                msgs = [
                    f'\nBranch {branch} does not exist at {repo_url}!',
                    'Using "master" branch for plugin, this may not work '
                    'with your RELEASE'
                ]

                for msg in msgs:
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'INFO',
                            'message': msg
                        },
                        _callback=callback
                    )

            # Time to make this reality
            repo.git.checkout(ref)
