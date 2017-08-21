# Copyright (c) 2014-2017, iocage
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
"""iocage create module."""
import json
import os
import pathlib
import subprocess as su
import sys
import uuid

import libzfs

import iocage.lib.ioc_common
import iocage.lib.ioc_destroy
import iocage.lib.ioc_exec
import iocage.lib.ioc_fstab
import iocage.lib.ioc_json
import iocage.lib.ioc_list
import iocage.lib.ioc_start
import iocage.lib.ioc_stop


class IOCCreate(object):
    """Create a jail from a clone."""

    def __init__(self, release, props, num, pkglist=None, plugin=False,
                 migrate=False, config=None, silent=False, template=False,
                 short=False, basejail=False, empty=False, uuid=None,
                 clone=False, exit_on_error=False, callback=None):
        self.pool = iocage.lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage.lib.ioc_json.IOCJson(self.pool).json_get_value(
            "iocroot")
        self.release = release
        self.props = props
        self.num = num
        self.pkglist = pkglist
        self.plugin = plugin
        self.migrate = migrate
        self.config = config
        self.template = template
        self.short = short
        self.basejail = basejail
        self.empty = empty
        self.uuid = uuid
        self.clone = clone
        self.silent = silent
        self.exit_on_error = exit_on_error
        self.callback = callback
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

    def create_jail(self):
        """Helper to catch SIGINT"""
        if self.uuid:
            jail_uuid = self.uuid
        else:
            jail_uuid = str(uuid.uuid4())

        if self.short:
            jail_uuid = jail_uuid[:8]

        location = f"{self.iocroot}/jails/{jail_uuid}"

        try:
            return self._create_jail(jail_uuid, location)
        except KeyboardInterrupt:
            iocage.lib.ioc_destroy.IOCDestroy().destroy_jail(location)
            sys.exit(1)

    def _create_jail(self, jail_uuid, location):
        """
        Create a snapshot of the user specified RELEASE dataset and clone a
        jail from that. The user can also specify properties to override the
        defaults.
        """
        start = False
        is_template = False

        if os.path.isdir(location) or os.path.isdir(
                f"{self.iocroot}/templates/{jail_uuid}"):
            raise RuntimeError(f"Jail: {jail_uuid} already exists!")

        if self.migrate:
            config = self.config
        else:
            try:
                if self.template:
                    _type = "templates"
                    temp_path = f"{self.iocroot}/{_type}/{self.release}"
                    template_config = iocage.lib.ioc_json.IOCJson(
                        temp_path).json_get_value
                    cloned_release = template_config("cloned_release")
                elif self.clone:
                    _type = "jails"
                    clone_path = f"{self.iocroot}/{_type}/{self.release}"
                    clone_config = iocage.lib.ioc_json.IOCJson(
                        clone_path).json_get_value
                    cloned_release = clone_config("cloned_release")
                    clone_uuid = clone_config("host_hostuuid")
                else:
                    _type = "releases"
                    rel_path = f"{self.iocroot}/{_type}/{self.release}"

                    freebsd_version = f"{rel_path}/root/bin/freebsd-version"

                    if not self.empty:
                        if self.release[:4].endswith("-"):
                            # 9.3-RELEASE and under don't actually have this
                            # binary.
                            cloned_release = self.release
                        else:
                            with open(freebsd_version, "r") as r:
                                for line in r:
                                    if line.startswith("USERLAND_VERSION"):
                                        # Long lines ftw?
                                        cl = line.rstrip().partition("=")[2]
                                        cloned_release = cl.strip('"')
                    else:
                        cloned_release = "EMPTY"
            except (IOError, OSError, FileNotFoundError, UnboundLocalError):
                # Unintuitevly a missing template will throw a
                # UnboundLocalError as the missing file will kick the
                # migration routine for zfs props. We don't need that :)
                if self.template:
                    raise RuntimeError(f"Template: {self.release} not found!")
                elif self.clone:
                    if os.path.isdir(f"{self.iocroot}/templates/"
                                     f"{self.release}"):
                        iocage.lib.ioc_common.logit({
                            "level"  : "EXCEPTION",
                            "message": "You cannot clone a template, "
                                       "use create -t instead."
                        }, exit_on_error=self.exit_on_error,
                            _callback=self.callback,
                            silent=self.silent)
                    else:
                        # Yep, self.release is actually the source jail.
                        iocage.lib.ioc_common.logit({
                            "level"  : "EXCEPTION",
                            "message": f"Jail: {self.release} not found!"
                        }, exit_on_error=self.exit_on_error,
                            _callback=self.callback,
                            silent=self.silent)
                else:
                    iocage.lib.ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": f"RELEASE: {self.release} not found!"
                    }, exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)

            if not self.clone:
                config = self.create_config(jail_uuid, cloned_release)
            else:
                clone_config = f"{self.iocroot}/jails/{jail_uuid}/config.json"
                clone_fstab = f"{self.iocroot}/jails/{jail_uuid}/fstab"

        jail = f"{self.pool}/iocage/jails/{jail_uuid}/root"

        if self.template:
            try:
                su.check_call(["zfs", "snapshot",
                               f"{self.pool}/iocage/templates/{self.release}/"
                               f"root@{jail_uuid}"], stderr=su.PIPE)
            except su.CalledProcessError:
                raise RuntimeError(f"Template: {self.release} not found!")

            su.Popen(["zfs", "clone", "-p",
                      f"{self.pool}/iocage/templates/{self.release}/root@"
                      f"{jail_uuid}", jail], stdout=su.PIPE).communicate()

            # self.release is actually the templates name
            config["release"] = iocage.lib.ioc_json.IOCJson(
                f"{self.iocroot}/templates/{self.release}").json_get_value(
                "release")
            config["cloned_release"] = iocage.lib.ioc_json.IOCJson(
                f"{self.iocroot}/templates/{self.release}").json_get_value(
                "cloned_release")
        elif self.clone:
            try:
                su.check_call(["zfs", "snapshot", "-r",
                               f"{self.pool}/iocage/jails/{self.release}"
                               f"@{jail_uuid}"], stderr=su.PIPE)
            except su.CalledProcessError:
                raise RuntimeError(f"Jail: {jail_uuid} not found!")

            su.Popen(["zfs", "clone",
                      f"{self.pool}/iocage/jails/{self.release}@"
                      f"{jail_uuid}", jail.replace("/root", "")],
                     stdout=su.PIPE).communicate()
            su.Popen(["zfs", "clone",
                      f"{self.pool}/iocage/jails/{self.release}/root@"
                      f"{jail_uuid}", jail], stdout=su.PIPE).communicate()

            with open(clone_config, "r") as _clone_config:
                config = json.load(_clone_config)

            # self.release is actually the clones name
            config["release"] = iocage.lib.ioc_json.IOCJson(
                f"{self.iocroot}/jails/{self.release}").json_get_value(
                "release")
            config["cloned_release"] = iocage.lib.ioc_json.IOCJson(
                f"{self.iocroot}/jails/{self.release}").json_get_value(
                "cloned_release")

            # Clones are expected to be as identical as possible.
            for k, v in config.items():
                v = v.replace(clone_uuid, jail_uuid)

                config[k] = v
        else:
            if not self.empty:
                dataset = f"{self.pool}/iocage/releases/{self.release}/" \
                          f"root@{jail_uuid}"
                try:
                    su.check_call(["zfs", "snapshot",
                                   f"{self.pool}/iocage/releases/"
                                   f"{self.release}/"
                                   f"root@{jail_uuid}"], stderr=su.PIPE)
                except su.CalledProcessError:
                    try:
                        snapshot = self.zfs.get_snapshot(dataset)
                        iocage.lib.ioc_common.logit({
                            "level"  : "EXCEPTION",
                            "message": f"Snapshot: {snapshot.name} exists!\n"
                                       "Please manually run zfs destroy"
                                       f" {snapshot.name} if you wish to "
                                       "destroy it."
                        }, exit_on_error=self.exit_on_error,
                            _callback=self.callback,
                            silent=self.silent)

                    except libzfs.ZFSException:
                        raise RuntimeError(
                            f"RELEASE: {self.release} not found!")

                su.Popen(["zfs", "clone", "-p",
                          f"{self.pool}/iocage/releases/{self.release}/root@"
                          f"{jail_uuid}", jail], stdout=su.PIPE).communicate()
            else:
                try:
                    iocage.lib.ioc_common.checkoutput(
                        ["zfs", "create", "-p", jail],
                        stderr=su.PIPE)
                except su.CalledProcessError as err:
                    raise RuntimeError(err.output.decode("utf-8").rstrip())

        iocjson = iocage.lib.ioc_json.IOCJson(location, silent=True)

        # This test is to avoid the same warnings during install_packages.
        if not self.plugin:
            for prop in self.props:
                key, _, value = prop.partition("=")

                if jail_uuid == "default":
                    iocage.lib.ioc_destroy.IOCDestroy(
                    ).__destroy_parse_datasets__(
                        f"{self.pool}/iocage/jails/{jail_uuid}")
                    iocage.lib.ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": "You cannot name a jail default, "
                                   "that is a reserved name."
                    }, exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)
                elif key == "boot" and value == "on" and not self.empty:
                    start = True
                elif key == "template" and value == "yes":
                    iocjson.json_write(config)  # Set counts on this.
                    location = location.replace("/jails/", "/templates/")

                    iocjson.json_set_value("type=template")
                    iocjson.json_set_value("template=yes")
                    iocjson.zfs_set_property(f"{self.pool}/iocage/templates/"
                                             f"{jail_uuid}", "readonly", "off")

                    # If you supply pkglist and templates without setting the
                    # config's type, you will end up with a type of jail
                    # instead of template like we want.
                    config["type"] = "template"
                    start = False
                    is_template = True

                try:
                    iocjson.json_check_prop(key, value, config)

                    config[key] = value
                except RuntimeError as err:
                    iocjson.json_write(config)  # Destroy counts on this.
                    iocage.lib.ioc_destroy.IOCDestroy().destroy_jail(location)

                    raise RuntimeError(f"***\n{err}\n***\n")
                except SystemExit:
                    iocjson.json_write(config)  # Destroy counts on this.
                    iocage.lib.ioc_destroy.IOCDestroy().destroy_jail(location)
                    exit(1)

            iocjson.json_write(config)

        # Just "touch" the fstab file, since it won't exist.
        if not self.clone:
            open(f"{location}/fstab", "wb").close()
        else:
            with open(clone_fstab, "r") as _clone_fstab:
                with iocage.lib.ioc_common.open_atomic(
                        clone_fstab, "w") as _fstab:
                    # open_atomic will empty the file, we need these still.
                    for line in _clone_fstab.readlines():
                        _fstab.write(line.replace(clone_uuid, jail_uuid))

        if not self.empty:
            self.create_rc(location, config["host_hostname"])

        if self.basejail:
            basedirs = ["bin", "boot", "lib", "libexec", "rescue", "sbin",
                        "usr/bin", "usr/include", "usr/lib",
                        "usr/libexec", "usr/sbin", "usr/share",
                        "usr/libdata", "usr/lib32"]

            if "-STABLE" in self.release:
                # HardenedBSD does not have this.
                basedirs.remove("usr/lib32")

            for bdir in basedirs:
                if "-RELEASE" not in self.release and "-STABLE" not in \
                        self.release:
                    _type = "templates"
                else:
                    _type = "releases"

                source = f"{self.iocroot}/{_type}/{self.release}/root/{bdir}"
                destination = f"{self.iocroot}/jails/{jail_uuid}/root/{bdir}"

                # This reduces the REFER of the basejail.
                # Just much faster by almost a factor of 2 than the builtins.
                su.Popen(["rm", "-r", "-f", destination]).communicate()
                os.mkdir(destination)

                iocage.lib.ioc_fstab.IOCFstab(jail_uuid, "add", source,
                                              destination, "nullfs", "ro", "0",
                                              "0", silent=True)
                config["basejail"] = "yes"

            iocjson.json_write(config)

        if self.empty:
            config["release"] = "EMPTY"
            config["cloned_release"] = "EMPTY"

            iocjson.json_write(config)

        if not self.plugin:
            if self.clone:
                msg = f"{jail_uuid} successfully cloned!"
            else:
                msg = f"{jail_uuid} successfully created!"

            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

        if self.pkglist:
            if config["ip4_addr"] == "none" and config["ip6_addr"] == "none" \
                    and config["dhcp"] != "on":
                iocage.lib.ioc_common.logit({
                    "level"  : "WARNING",
                    "message": "You need an IP address for the jail to"
                               " install packages!\n"
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                self.create_install_packages(jail_uuid, location, config)

        if start:
            iocage.lib.ioc_start.IOCStart(jail_uuid, location, config,
                                          silent=self.silent)

        if is_template:
            # We have to set readonly back, since we're done with our tasks
            iocjson.zfs_set_property(f"{self.pool}/iocage/templates/"
                                     f"{jail_uuid}", "readonly", "on")
        return jail_uuid

    def create_config(self, jail_uuid, release):
        """
        Loads default props and sets the user properties, along with some mild
        sanity checking
        """
        ioc_json = iocage.lib.ioc_json.IOCJson()
        jail_props = ioc_json.json_check_default_config()

        # Unique jail properties, they will be overridden by user supplied
        # values.
        jail_props["host_hostname"] = jail_uuid
        jail_props["host_hostuuid"] = jail_uuid
        jail_props["release"] = release
        jail_props["cloned_release"] = self.release
        jail_props["jail_zfs_dataset"] = f"iocage/jails/{jail_uuid}/data"
        jail_props["depends"] = "none"

        return jail_props

    def create_install_packages(self, jail_uuid, location, config,
                                repo="pkg.freebsd.org", site="FreeBSD"):
        """
        Takes a list of pkg's to install into the target jail. The resolver
        property is required for pkg to have network access.
        """
        status, jid = iocage.lib.ioc_list.IOCList().list_get_jid(jail_uuid)
        err = False

        if not status:
            iocage.lib.ioc_start.IOCStart(jail_uuid, location, config,
                                          silent=True)
            status, jid = iocage.lib.ioc_list.IOCList().list_get_jid(jail_uuid)

        # Connectivity test courtesy David Cottlehuber off Google Group
        srv_connect_cmd = ["drill", f"_http._tcp.{repo}", "SRV"]
        dnssec_connect_cmd = ["drill", "-D", f"{repo}"]

        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": f"Testing SRV response to {site}"
        },
            _callback=self.callback,
            silent=self.silent)
        srv_connection, srv_err = iocage.lib.ioc_exec.IOCExec(
            srv_connect_cmd, jail_uuid, location, plugin=self.plugin,
            silent=True).exec_jail()

        if srv_err:
            raise RuntimeError(f"{srv_connection}\n"
                               f"Command run: {' '.join(srv_connect_cmd)}")

        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": f"Testing DNSSEC response to {site}"
        },
            _callback=self.callback,
            silent=self.silent)
        dnssec_connection, dnssec_err = iocage.lib.ioc_exec.IOCExec(
            dnssec_connect_cmd, jail_uuid, location, plugin=self.plugin,
            exit_on_error=self.exit_on_error, silent=True).exec_jail()

        if dnssec_err:
            raise RuntimeError(f"{dnssec_connection}\n"
                               f"Command run: {' '.join(dnssec_connect_cmd)}")

        if isinstance(self.pkglist, str):
            with open(self.pkglist, "r") as j:
                self.pkglist = json.load(j)["pkgs"]

        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": "\nInstalling pkg... "
        },
            _callback=self.callback,
            silent=self.silent)
        # To avoid a user being prompted about pkg.
        su.Popen(["pkg-static", "-j", jid, "install", "-q", "-y",
                  "pkg"], stderr=su.PIPE).communicate()

        # We will have mismatched ABI errors from earlier, this is to be safe.
        os.environ["ASSUME_ALWAYS_YES"] = "yes"
        cmd = ("pkg-static", "upgrade", "-f", "-q", "-y")
        pkg_upgrade, pkgupgrade_err = iocage.lib.ioc_exec.IOCExec(
            cmd, jail_uuid, location, plugin=self.plugin,
            exit_on_error=self.exit_on_error).exec_jail()

        if pkgupgrade_err:
            iocage.lib.ioc_common.logit({
                "level"  : "ERROR",
                "message": f"{pkg_upgrade}"
            },
                _callback=self.callback,
                silent=self.silent)
            err = True

        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": "Installing supplied packages:"
        },
            _callback=self.callback,
            silent=self.silent)
        for pkg in self.pkglist:
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": f"  - {pkg}... "
            },
                _callback=self.callback,
                silent=self.silent)
            cmd = ("pkg", "install", "-q", "-y", pkg)
            pkg_install, pkg_err = iocage.lib.ioc_exec.IOCExec(
                cmd, jail_uuid, location, plugin=self.plugin,
                exit_on_error=self.exit_on_error,
                silent=self.silent).exec_jail()

            if pkg_err:
                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"{pkg_err.decode()}"
                },
                    _callback=self.callback,
                    silent=self.silent)
                err = True

        os.remove(f"{location}/root/etc/resolv.conf")

        if status:
            iocage.lib.ioc_stop.IOCStop(jail_uuid, location, config,
                                        silent=True)

        if self.plugin and err:
            return err

    @staticmethod
    def create_rc(location, host_hostname):
        """
        Writes a boilerplate rc.conf file for a jail if it doesn't exist,
         otherwise changes the hostname.
        """
        rc_conf = pathlib.Path(f"{location}/root/etc/rc.conf")

        if rc_conf.is_file():
            su.Popen(["sysrc", "-R", f"{location}/root",
                      f"host_hostname={host_hostname}"],
                     stdout=su.PIPE).communicate()
        else:
            rcconf = """\
host_hostname="{hostname}"
cron_flags="$cron_flags -J 15"

# Disable Sendmail by default
sendmail_enable="NONE"
sendmail_submit_enable="NO"
sendmail_outbound_enable="NO"
sendmail_msp_queue_enable="NO"

# Run secure syslog
syslogd_flags="-c -ss"

# Enable IPv6
ipv6_activate_all_interfaces=\"YES\"
"""
            rc_conf.write_text(rcconf.format(hostname=host_hostname))
