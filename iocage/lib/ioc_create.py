"""iocage create module."""
import json

import os
import uuid
from datetime import datetime
from shutil import copy
from subprocess import CalledProcessError, PIPE, Popen, check_call

from iocage.lib.ioc_common import checkoutput
from iocage.lib.ioc_exec import IOCExec
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart
from iocage.lib.ioc_stop import IOCStop
import iocage.lib.ioc_log as ioc_log


class IOCCreate(object):
    """Create a jail from a clone."""

    def __init__(self, release, props, num, pkglist=None, plugin=False,
                 migrate=False, config=None, silent=False, template=False,
                 short=False, basejail=False, empty=False, uuid=None):
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
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
        self.lgr = ioc_log.getLogger('ioc_create')

        if silent:
            self.lgr.disabled = True

    def create_jail(self):
        """
        Create a snapshot of the user specified RELEASE dataset and clone a
        jail from that. The user can also specify properties to override the
        defaults.
        """
        start = False

        if self.uuid:
            jail_uuid = self.uuid
        else:
            jail_uuid = str(uuid.uuid4())

        if self.short:
            jail_uuid = jail_uuid[:8]

        location = "{}/jails/{}".format(self.iocroot, jail_uuid)

        if os.path.isdir(location):
            raise RuntimeError("The UUID is already in use by another jail.")

        if self.migrate:
            config = self.config
        else:
            if self.template:
                _type = "templates"
            else:
                _type = "releases"

            freebsd_version = "{}/{}/{}/root/bin/freebsd-version".format(
                self.iocroot, _type, self.release)

            try:
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

                config = self.create_config(jail_uuid, cloned_release)
            except (IOError, OSError):
                if self.template:
                    raise RuntimeError("Template: {} not found!".format(
                        self.release))
                else:
                    raise RuntimeError("RELEASE: {} not found!".format(
                        self.release))

        jail = "{}/iocage/jails/{}/root".format(self.pool, jail_uuid)

        if self.template:
            try:
                check_call(["zfs", "snapshot",
                            "{}/iocage/templates/{}/root@{}".format(
                                self.pool, self.release, jail_uuid)],
                           stderr=PIPE)
            except CalledProcessError:
                raise RuntimeError("Template: {} not found!".format(
                    self.release))

            Popen(["zfs", "clone", "-p",
                   "{}/iocage/templates/{}/root@{}".format(
                       self.pool, self.release, jail_uuid),
                   jail], stdout=PIPE).communicate()

            # self.release is actually the templates name
            config["release"] = IOCJson("{}/templates/{}".format(
                self.iocroot, self.release)).json_get_value("release")
            config["cloned_release"] = IOCJson("{}/templates/{}".format(
                self.iocroot, self.release)).json_get_value("cloned_release")
        else:
            if not self.empty:
                try:
                    check_call(["zfs", "snapshot",
                                "{}/iocage/releases/{}/root@{}".format(
                                    self.pool, self.release, jail_uuid)],
                               stderr=PIPE)
                except CalledProcessError:
                    raise RuntimeError(
                        "RELEASE: {} not found!".format(self.release))

                Popen(["zfs", "clone", "-p",
                       "{}/iocage/releases/{}/root@{}".format(
                           self.pool, self.release, jail_uuid),
                       jail], stdout=PIPE).communicate()
            else:
                try:
                    checkoutput(["zfs", "create", "-p", jail], stderr=PIPE)
                except CalledProcessError as err:
                    raise RuntimeError(err.output.decode("utf-8").rstrip())

        iocjson = IOCJson(location)

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
                    from iocage.lib.ioc_destroy import IOCDestroy
                    iocjson.json_write(config)  # Destroy counts on this.
                    IOCDestroy(jail_uuid, "", location,
                               silent=True).destroy_jail()
                    raise RuntimeError(f"***\n{err}\n***\n")

            iocjson.json_write(config)

        # Just "touch" the fstab file, since it won't exist.
        open("{}/jails/{}/fstab".format(self.iocroot, jail_uuid), "wb").close()
        _tag = self.create_link(jail_uuid, config["tag"])
        config["tag"] = _tag

        if not self.empty:
            self.create_rc(location, config["host_hostname"])

        if self.basejail:
            from iocage.lib.ioc_fstab import IOCFstab
            basedirs = ["bin", "boot", "lib", "libexec", "rescue", "sbin",
                        "usr/bin", "usr/include", "usr/lib",
                        "usr/libexec", "usr/sbin", "usr/share",
                        "usr/libdata", "usr/lib32"]

            for bdir in basedirs:
                source = f"{self.iocroot}/releases/{self.release}/root/{bdir}"
                destination = f"{self.iocroot}/jails/{jail_uuid}/root/{bdir}"

                IOCFstab(jail_uuid, _tag, "add", source, destination, "nullfs",
                         "ro", "0", "0", silent=True)
                config["basejail"] = "yes"

            iocjson.json_write(config)

        if self.empty:
            config["release"] = "EMPTY"
            config["cloned_release"] = "EMPTY"

            iocjson.json_write(config)

        if not self.plugin:
            self.lgr.info(
                "{} ({}) successfully created!".format(jail_uuid, _tag))

        if self.pkglist:
            if config["ip4_addr"] == "none" and config["ip6_addr"] == "none":
                self.lgr.warning(" WARNING: You need an IP address for the"
                                 " jail to install packages!\n")
            else:
                self.create_install_packages(jail_uuid, location, _tag, config)

        if start:
            from iocage.lib.ioc_start import IOCStart

            IOCStart(jail_uuid, _tag, location, config)

        return jail_uuid

    def create_config(self, jail_uuid, release):
        """
        This sets up the default configuration for a jail. It also does some
        mild sanity checking on the properties users are supplying.
        """
        version = IOCJson().json_get_version()

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
            "tag"                  : datetime.utcnow().strftime("%F@%T:%f"),
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
            "jail_zfs_dataset"     : "iocage/jails/{}/data".format(jail_uuid),
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

    def create_install_packages(self, jail_uuid, location, _tag, config):
        """
        Takes a list of pkg's to install into the target jail. The resolver
        property is required for pkg to have network access.
        """
        status, jid = IOCList().list_get_jid(jail_uuid)
        err = False
        if not status:
            IOCStart(jail_uuid, _tag, location, config, silent=True)
            resolver = config["resolver"]

            if resolver != "/etc/resolv.conf" and resolver != "none":
                with open("{}/etc/resolv.conf".format(location),
                          "w") as resolv_conf:
                    for line in resolver.split(";"):
                        resolv_conf.write(line + "\n")
            else:
                copy(resolver, "{}/root/etc/resolv.conf".format(location))

            status, jid = IOCList().list_get_jid(jail_uuid)

        # Connectivity test courtesy David Cottlehuber off Google Group
        srv_connect_cmd = ["drill", "_http._tcp.pkg.freebsd.org", "SRV"]
        dnssec_connect_cmd = ["drill", "-D", "pkg.freebsd.org"]

        self.lgr.info("Testing SRV response to FreeBSD")
        srv_connection = IOCExec(srv_connect_cmd, jail_uuid, _tag, location,
                                 plugin=self.plugin).exec_jail()

        if srv_connection:
            raise RuntimeError(f"ERROR: {srv_connection}\n"
                               f"Command run: {' '.join(srv_connect_cmd)}")

        self.lgr.info("Testing DNSSEC response to FreeBSD")
        dnssec_connection = IOCExec(dnssec_connect_cmd, jail_uuid, _tag,
                                    location, plugin=self.plugin).exec_jail()

        if dnssec_connection:
            raise RuntimeError(f"ERROR: {dnssec_connection}\n"
                               f"Command run: {' '.join(dnssec_connect_cmd)}")

        if not self.plugin:
            with open(self.pkglist, "r") as j:
                self.pkglist = json.load(j)["pkgs"]

        self.lgr.info("\nInstalling pkg... ")
        # To avoid a user being prompted about pkg.
        Popen(["pkg-static", "-j", jid, "install", "-q", "-y",
               "pkg"], stderr=PIPE).communicate()

        # We will have mismatched ABI errors from earlier, this is to be safe.
        os.environ["ASSUME_ALWAYS_YES"] = "yes"
        cmd = ("pkg-static", "upgrade", "-f", "-q", "-y")
        pkg_upgrade = IOCExec(cmd, jail_uuid, _tag, location,
                              plugin=self.plugin).exec_jail()

        if pkg_upgrade:
            self.lgr.error(f"ERROR: {pkg_upgrade}")
            err = True

        self.lgr.info("Installing supplied packages:")
        for pkg in self.pkglist:
            self.lgr.info("  - {}... ".format(pkg))
            cmd = ("pkg", "install", "-q", "-y", pkg)
            pkg_install = IOCExec(cmd, jail_uuid, _tag, location,
                                  plugin=self.plugin).exec_jail()

            if pkg_install:
                self.lgr.error("ERROR: {}".format(pkg_install))
                err = True

        os.remove("{}/root/etc/resolv.conf".format(location))

        if status:
            IOCStop(jail_uuid, _tag, location, config, silent=True)

        if self.plugin and err:
            return err

    def create_link(self, jail_uuid, tag, old_tag=None):
        """
        Creates a symlink from iocroot/jails/jail_uuid to iocroot/tags/tag
        """
        # If this exists, another jail has used this tag.
        try:
            readlink_mount = os.readlink(
                "{}/tags/{}".format(self.iocroot, tag))
            readlink_uuid = [m for m in readlink_mount.split("/") if len(m)
                             == 36 or len(m) == 8][0]
        except OSError:
            pass

        tag_date = datetime.utcnow().strftime("%F@%T:%f")
        jail_location = "{}/jails/{}".format(self.iocroot, jail_uuid)

        if not os.path.exists("{}/tags".format(self.iocroot)):
            os.mkdir("{}/tags".format(self.iocroot))

        if not os.path.exists("{}/tags/{}".format(self.iocroot, tag)):
            # We can have stale tags sometimes that aren't valid
            try:
                os.remove("{}/tags/{}".format(self.iocroot, tag))
            except OSError:
                pass

            try:
                os.remove("{}/tags/{}".format(self.iocroot, old_tag))
            except OSError:
                pass
            finally:
                os.symlink(jail_location, "{}/tags/{}".format(self.iocroot,
                                                              tag))

                return tag
        else:
            self.lgr.warning("\n  WARNING: tag: \"{}\" in use by {}!\n".format(
                tag, readlink_uuid) + "  Renaming {}'s tag to {}.\n".format(
                jail_uuid, tag_date))

            os.symlink(jail_location, "{}/tags/{}".format(self.iocroot,
                                                          tag_date))
            IOCJson(jail_location, silent=True).json_set_value(
                "tag={}".format(tag_date), create_func=True)

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

        with open("{}/root/etc/rc.conf".format(location), "w") as rc_conf:
            rc_conf.write(rcconf.format(hostname=host_hostname))
