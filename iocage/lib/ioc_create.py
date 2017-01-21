"""iocage create module."""
import json
import logging
import uuid
from datetime import datetime
from shutil import copy
from subprocess import CalledProcessError, PIPE, Popen, check_call

import os

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart


class IOCCreate(object):
    """Create a jail from a clone."""

    def __init__(self, release, props, num, pkglist=None, plugin=False,
                 migrate=False, config=None, silent=False, template=False):
        self.pool = IOCJson().get_prop_value("pool")
        self.iocroot = IOCJson(self.pool).get_prop_value("iocroot")
        self.release = release
        self.props = props
        self.num = num
        self.pkglist = pkglist
        self.plugin = plugin
        self.migrate = migrate
        self.config = config
        self.template = template
        self.lgr = logging.getLogger('ioc_create')

        if silent:
            self.lgr.disabled = True

    def create_jail(self):
        """
        Create a snapshot of the user specified RELEASE dataset and clone a jail
        jail from that. The user can also specify properties to override the
        defaults.
        """
        jail_uuid = str(uuid.uuid4())
        location = "{}/jails/{}".format(self.iocroot, jail_uuid)

        if self.migrate:
            config = self.config
        else:
            config = self.create_config(jail_uuid)

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
                self.iocroot, self.release)).get_prop_value("release")

        else:
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

        IOCJson(location).write_json(config)

        # Just "touch" the fstab file, since it won't exist.
        open("{}/jails/{}/fstab".format(self.iocroot, jail_uuid), 'w').close()
        _tag = self.create_link(jail_uuid, config["tag"])
        self.create_rc(location, config["host_hostname"])

        self.lgr.info("{} ({}) successfully created!".format(_tag, jail_uuid))

        if self.pkglist:
            if config["ip4_addr"] == "none":
                self.lgr.error(" ERROR: You need an IP address for the jail"
                               " to install packages!\n")
            else:
                self.install_packages(jail_uuid, location, _tag, config)

        if self.plugin or self.migrate:
            return jail_uuid

    def create_config(self, jail_uuid):
        """
        This sets up the default configuration for a jail. It also does some
        mild sanity checking on the properties users are supplying.
        """
        version = IOCJson().iocage_version()

        with open('/etc/hostid', 'r') as _file:
            hostid = _file.read().strip()

        default_props = {
            "CONFIG_VERSION"       : version,
            # Network properties
            "ipv6"                 : "off",
            "interfaces"           : "vnet0:bridge0,vnet1:bridge1",
            "host_domainname"      : "none",
            "host_hostname"        : jail_uuid,
            "exec_fib"             : "0",
            "ip4_addr"             : "none",
            "ip4_autostart"        : "none",
            "ip4_autoend"          : "none",
            "ip4_autosubnet"       : "none",
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
            "memoryuse"            : "8G:log",
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
            "istemplate"           : "no",
            "bpf"                  : "off",
            "dhcp"                 : "off",
            "boot"                 : "off",
            "notes"                : "none",
            "owner"                : "root",
            "priority"             : "99",
            "last_started"         : "none",
            "release"              : self.release,
            "template"             : "none",
            "hostid"               : hostid,
            "jail_zfs"             : "off",
            "jail_zfs_dataset"     : "iocage/jails/{}/data".format(jail_uuid),
            "jail_zfs_mountpoint"  : "none",
            "mount_procfs"         : "0",
            "mount_linprocfs"      : "0",
            "hack88"               : "0",
            "count"                : "1",
            "vnet"                 : "off",
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
            # Git properties
            "gitlocation"          : "https://github.com"
        }

        if self.plugin:
            for key, value in self.props.items():
                default_props[key] = value
        else:
            for prop in self.props:
                key, _, value = prop.partition("=")

                if key in default_props.keys():
                    if self.num != 0:
                        if key == "tag":
                            value = "{}_{}".format(value, self.num)
                    default_props[key] = value
                else:
                    raise RuntimeError("Invalid property:"
                                       " {} specified!".format(key))

        return default_props

    def install_packages(self, jail_uuid, location, _tag, config):
        """
        Takes a list of pkg's to install into the target jail. The resolver
        property is required for pkg to have network access.
        """
        self.lgr.info("{0}, starting jail.".format(
            "\n{} ({}) is not running".format(jail_uuid, _tag)))
        IOCStart(jail_uuid, location, silent=True).start_jail(_tag, config)
        _, jid = IOCList().get_jid(jail_uuid)
        resolver = config["resolver"]

        if resolver != "/etc/resolv.conf" and resolver != "none":
            with open("{}/etc/resolv.conf".format(location),
                      "w") as resolv_conf:
                for line in resolver.split(";"):
                    resolv_conf.write(line + "\n")
        else:
            copy(resolver, "{}/root/etc/resolv.conf".format(location))

        if not self.plugin:
            with open(self.pkglist) as j:
                self.pkglist = json.load(j)["pkgs"]

        # TODO: Fancier.
        self.lgr.info("\nUpdating pkg repository... ")
        # We can get some annoying mismatch warnings.
        Popen(["pkg", "-j", jid, "update"], stderr=PIPE,
              stdout=PIPE).communicate()

        self.lgr.info("Installing supplied packages:")
        for pkg in self.pkglist:
            # TODO: Fancier.
            self.lgr.info("  - {}... ".format(pkg))
            Popen(["pkg", "-j", jid, "install", "-q", "-y", pkg],
                  stderr=PIPE, stdout=PIPE).communicate()

        os.remove("{}/root/etc/resolv.conf".format(location))

    def create_link(self, jail_uuid, tag, old_tag=None):
        """
        Creates a symlink from iocroot/jails/jail_uuid to iocroot/tags/tag
        """
        # If this exists, another jail has used this tag.
        try:
            readlink_mount = os.readlink(
                "{}/tags/{}".format(self.iocroot, tag))
            readlink_uuid = readlink_mount.split("/")[3]
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
            IOCJson(jail_location, silent=True).set_prop_value(
                "tag={}".format(tag_date), create_func=True)

            return tag_date

    def create_rc(self, location, host_hostname):
        """Writes a boilerplate rc.conf file for a jail."""
        rcconf = """\
host_hostname=\"{hostname}\"
cron_flags=\"$cron_flags -J 15\"

# Disable Sendmail by default
sendmail_enable=\"NONE\"
sendmail_submit_enable=\"NO\"
sendmail_outbound_enable=\"NO\"
sendmail_msp_queue_enable=\"NO\"

# Run secure syslog
syslogd_flags=\"-c -ss\"

# Enable IPv6
ipv6_activate_all_interfaces=\"YES\"
"""

        with open("{}/root/etc/rc.conf".format(location), "w") as rc_conf:
            rc_conf.write(rcconf.format(hostname=host_hostname))
