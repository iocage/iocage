"""iocage create module."""
import datetime
import json
import os
import shutil
import subprocess as su
import sys
import uuid

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
                 callback=None):
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
        self.silent = silent
        self.callback = callback

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

        if os.path.isdir(location):
            raise RuntimeError("The UUID is already in use by another jail.")

        if self.migrate:
            config = self.config
        else:
            try:
                if self.template:
                    _type = "templates"
                    temp_path = f"{self.iocroot}/{_type}/{self.release}"
                    template_config = iocage.lib.ioc_json.IOCJson(
                        f"{temp_path}").json_get_value
                    cloned_release = template_config("cloned_release")
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
                else:
                    raise RuntimeError(f"RELEASE: {self.release} not found!")

            config = self.create_config(jail_uuid, cloned_release)
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
        else:
            if not self.empty:
                try:
                    su.check_call(["zfs", "snapshot",
                                   f"{self.pool}/iocage/releases/"
                                   f"{self.release}/"
                                   f"root@{jail_uuid}"], stderr=su.PIPE)
                except su.CalledProcessError:
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

        iocjson = iocage.lib.ioc_json.IOCJson(location)

        # This test is to avoid the same warnings during install_packages.
        if not self.plugin:
            for prop in self.props:
                key, _, value = prop.partition("=")

                if self.num != 0:
                    if key == "tag":
                        value = f"{value}_{self.num}"
                elif key == "boot" and value == "on":
                    start = True

                try:
                    iocjson.json_check_prop(key, value, config)

                    config[key] = value
                except RuntimeError as err:
                    iocjson.json_write(config)  # Destroy counts on this.
                    iocage.lib.ioc_destroy.IOCDestroy().destroy_jail(location)
                    raise RuntimeError(f"***\n{err}\n***\n")

            iocjson.json_write(config)

        # Just "touch" the fstab file, since it won't exist.
        open(f"{self.iocroot}/jails/{jail_uuid}/fstab", "wb").close()
        _tag = self.create_link(jail_uuid, config["tag"])
        config["tag"] = _tag

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

                iocage.lib.ioc_fstab.IOCFstab(jail_uuid, _tag, "add", source,
                                              destination,
                                              "nullfs", "ro", "0", "0",
                                              silent=True)
                config["basejail"] = "yes"

            iocjson.json_write(config)

        if self.empty:
            config["release"] = "EMPTY"
            config["cloned_release"] = "EMPTY"

            iocjson.json_write(config)

        if not self.plugin:
            msg = f"{jail_uuid} ({_tag}) successfully created!"
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

        if self.pkglist:
            if config["ip4_addr"] == "none" and config["ip6_addr"] == "none":
                iocage.lib.ioc_common.logit({
                    "level"  : "WARNING",
                    "message": " You need an IP address for the jail to"
                               "install packages!\n"
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                self.create_install_packages(jail_uuid, location, _tag, config)

        if start:
            iocage.lib.ioc_start.IOCStart(jail_uuid, _tag, location, config,
                                          silent=self.silent)

        return jail_uuid

    def create_config(self, jail_uuid, release):
        """
        This sets up the default configuration for a jail. It also does some
        mild sanity checking on the properties users are supplying.
        """
        version = iocage.lib.ioc_json.IOCJson().json_get_version()

        with open("/etc/hostid", "r") as _file:
            hostid = _file.read().strip()

        default_props = {
            "CONFIG_VERSION"       : version,
            # Network properties
            "interfaces"           : "vnet0:bridge0",
            "host_domainname"      : "none",
            "host_hostname"        : jail_uuid,
            "exec_fib"             : "0",
            "ip4_addr"             : "none",
            "ip4_saddrsel"         : "1",
            "ip4"                  : "new",
            "ip6_addr"             : "none",
            "ip6_saddrsel"         : "1",
            "ip6"                  : "new",
            "defaultrouter"        : "none",
            "defaultrouter6"       : "none",
            "resolver"             : "/etc/resolv.conf",
            "mac_prefix"           : "02ff60",
            "vnet0_mac"            : "none",
            "vnet1_mac"            : "none",
            "vnet2_mac"            : "none",
            "vnet3_mac"            : "none",
            # Jail Properties
            "devfs_ruleset"        : "4",
            "exec_start"           : "/bin/sh /etc/rc",
            "exec_stop"            : "/bin/sh /etc/rc.shutdown",
            "exec_prestart"        : "/usr/bin/true",
            "exec_poststart"       : "/usr/bin/true",
            "exec_prestop"         : "/usr/bin/true",
            "exec_poststop"        : "/usr/bin/true",
            "exec_clean"           : "1",
            "exec_timeout"         : "60",
            "stop_timeout"         : "30",
            "exec_jail_user"       : "root",
            "exec_system_jail_user": "0",
            "exec_system_user"     : "root",
            "mount_devfs"          : "1",
            "mount_fdescfs"        : "1",
            "enforce_statfs"       : "2",
            "children_max"         : "0",
            "login_flags"          : "-f root",
            "securelevel"          : "2",
            "sysvmsg"              : "new",
            "sysvsem"              : "new",
            "sysvshm"              : "new",
            "host_hostuuid"        : jail_uuid,
            "allow_set_hostname"   : "1",
            "allow_sysvipc"        : "0",
            "allow_raw_sockets"    : "0",
            "allow_chflags"        : "0",
            "allow_mount"          : "0",
            "allow_mount_devfs"    : "0",
            "allow_mount_nullfs"   : "0",
            "allow_mount_procfs"   : "0",
            "allow_mount_tmpfs"    : "0",
            "allow_mount_zfs"      : "0",
            "allow_quotas"         : "0",
            "allow_socket_af"      : "0",
            # RCTL limits
            "cpuset"               : "off",
            "rlimits"              : "off",
            "memoryuse"            : "off",
            "memorylocked"         : "off",
            "vmemoryuse"           : "off",
            "maxproc"              : "off",
            "cputime"              : "off",
            "pcpu"                 : "off",
            "datasize"             : "off",
            "stacksize"            : "off",
            "coredumpsize"         : "off",
            "openfiles"            : "off",
            "pseudoterminals"      : "off",
            "swapuse"              : "off",
            "nthr"                 : "off",
            "msgqqueued"           : "off",
            "msgqsize"             : "off",
            "nmsgq"                : "off",
            "nsemop"               : "off",
            "nshm"                 : "off",
            "shmsize"              : "off",
            "wallclock"            : "off",
            # Custom properties
            "type"                 : "jail",
            "tag"                  : datetime.datetime.utcnow().strftime(
                "%F@%T:%f"),
            "bpf"                  : "off",
            "dhcp"                 : "off",
            "boot"                 : "off",
            "notes"                : "none",
            "owner"                : "root",
            "priority"             : "99",
            "last_started"         : "none",
            "release"              : release,
            "cloned_release"       : self.release,
            "template"             : "no",
            "hostid"               : hostid,
            "jail_zfs"             : "off",
            "jail_zfs_dataset"     : f"iocage/jails/{jail_uuid}/data",
            "jail_zfs_mountpoint"  : "none",
            "mount_procfs"         : "0",
            "mount_linprocfs"      : "0",
            "count"                : "1",
            "vnet"                 : "off",
            "basejail"             : "no",
            "comment"              : "none",
            # Sync properties
            "sync_state"           : "none",
            "sync_target"          : "none",
            "sync_tgt_zpool"       : "none",
            # Native ZFS properties
            "compression"          : "lz4",
            "origin"               : "readonly",
            "quota"                : "none",
            "mountpoint"           : "readonly",
            "compressratio"        : "readonly",
            "available"            : "readonly",
            "used"                 : "readonly",
            "dedup"                : "off",
            "reservation"          : "none",
        }

        return default_props

    def create_install_packages(self, jail_uuid, location, _tag, config,
                                repo="pkg.freebsd.org", site="FreeBSD"):
        """
        Takes a list of pkg's to install into the target jail. The resolver
        property is required for pkg to have network access.
        """
        status, jid = iocage.lib.ioc_list.IOCList().list_get_jid(jail_uuid)
        err = False
        if not status:
            iocage.lib.ioc_start.IOCStart(jail_uuid, _tag, location, config,
                                          silent=True)
            resolver = config["resolver"]

            if resolver != "/etc/resolv.conf" and resolver != "none":
                with open(f"{location}/etc/resolv.conf", "w") as resolv_conf:
                    for line in resolver.split(";"):
                        resolv_conf.write(line + "\n")
            else:
                shutil.copy(resolver, f"{location}/root/etc/resolv.conf")

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
            srv_connect_cmd, jail_uuid, _tag, location,
            plugin=self.plugin).exec_jail()

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
            dnssec_connect_cmd, jail_uuid, _tag, location,
            plugin=self.plugin).exec_jail()

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
            cmd, jail_uuid, _tag, location, plugin=self.plugin).exec_jail()

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
                cmd, jail_uuid, _tag, location, plugin=self.plugin).exec_jail()

            if pkg_err:
                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"{pkg_install}"
                },
                    _callback=self.callback,
                    silent=self.silent)
                err = True

        os.remove(f"{location}/root/etc/resolv.conf")

        if status:
            iocage.lib.ioc_stop.IOCStop(jail_uuid, _tag, location, config,
                                        silent=True)

        if self.plugin and err:
            return err

    def create_link(self, jail_uuid, tag, old_tag=None):
        """
        Creates a symlink from iocroot/jails/jail_uuid to iocroot/tags/tag
        """
        # If this exists, another jail has used this tag.
        try:
            readlink_mount = os.readlink(f"{self.iocroot}/tags/{tag}")
            readlink_uuid = [m for m in readlink_mount.split("/") if len(m)
                             == 36 or len(m) == 8][0]
        except OSError:
            pass

        tag_date = datetime.datetime.utcnow().strftime("%F@%T:%f")
        jail_location = f"{self.iocroot}/jails/{jail_uuid}"

        if not os.path.exists(f"{self.iocroot}/tags"):
            os.mkdir(f"{self.iocroot}/tags")

        if not os.path.exists(f"{self.iocroot}/tags/{tag}"):
            # We can have stale tags sometimes that aren't valid
            try:
                os.remove(f"{self.iocroot}/tags/{tag}")
            except OSError:
                pass

            try:
                os.remove(f"{self.iocroot}/tags/{old_tag}")
            except OSError:
                pass
            finally:
                os.symlink(jail_location, f"{self.iocroot}/tags/{tag}")

                return tag
        else:
            iocage.lib.ioc_common.logit({
                "level"  : "WARNING",
                "message": f"\n  tag: \"{tag}\" in use by {readlink_uuid}!\n"
                           f"  Renaming {jail_uuid}'s tag to {tag_date}.\n"
            },
                _callback=self.callback,
                silent=self.silent)

            os.symlink(jail_location, f"{self.iocroot}/tags/{tag_date}")
            iocage.lib.ioc_json.IOCJson(jail_location,
                                        silent=True).json_set_value(
                f"tag={tag_date}", create_func=True)

            return tag_date

    def create_rc(self, location, host_hostname):
        """Writes a boilerplate rc.conf file for a jail."""
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

        with open(f"{location}/root/etc/rc.conf", "w") as rc_conf:
            rc_conf.write(rcconf.format(hostname=host_hostname))
