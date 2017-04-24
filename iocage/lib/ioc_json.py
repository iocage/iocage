"""Convert, load or write JSON."""
import json
import logging
import os
import re
import sys
from os import geteuid, path
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_call

from iocage.lib.ioc_common import checkoutput, get_nested_key, open_atomic


def _get_pool_and_iocroot():
    """For internal setting of pool and iocroot."""
    pool = IOCJson().json_get_value("pool")
    iocroot = IOCJson(pool).json_get_value("iocroot")

    return (pool, iocroot)


class IOCJson(object):
    """
    Migrates old iocage configurations(UCL and ZFS Props) to the new JSON
    format, will set and get properties.
    """

    def __init__(self, location="", silent=False, cli=False):
        self.location = location
        self.lgr = logging.getLogger('ioc_json')
        self.cli = cli

        if silent:
            self.lgr.disabled = True

    def json_convert_from_ucl(self):
        """Convert to JSON. Accepts a location to the ucl configuration."""
        if geteuid() != 0:
            raise RuntimeError("You need to be root to convert the"
                               " configurations to the new format!")

        with open(self.location + "/config", "r") as conf:
            lines = conf.readlines()

        key_and_value = {}

        for line in lines:
            line = line.partition("=")
            key = line[0].rstrip()
            value = line[2].replace(";", "").replace('"', '').strip()

            key_and_value[key] = value

        self.json_write(key_and_value)

    def json_convert_from_zfs(self, uuid, skip=False):
        """Convert to JSON. Accepts a jail UUID"""
        pool, _ = _get_pool_and_iocroot()
        dataset = "{}/iocage/jails/{}".format(pool, uuid)
        jail_zfs_prop = "org.freebsd.iocage:jail_zfs_dataset"

        if geteuid() != 0:
            raise RuntimeError("You need to be root to convert the"
                               " configurations to the new format!")

        cmd = ["zfs", "get", "-H", "-o", "property,value", "all", dataset]

        regex = re.compile("org.freebsd.iocage")

        zfs_get = Popen(cmd, stdout=PIPE).communicate()[0].decode(
            "utf-8").split("\n")

        # Find each of the props we want to convert.
        props = [p for p in zfs_get if re.search(regex, p)]

        key_and_value = {"host_domainname": "none"}

        for prop in props:
            prop = prop.partition(":")
            key = prop[2].split("\t")[0]
            value = prop[2].split("\t")[1].strip()

            if key == "type":
                if value == "basejail":
                    # These were just clones on master.
                    value = "jail"
                    key_and_value["basejail"] = "yes"
            elif key == "hostname":
                hostname = key_and_value["host_hostname"]

                if value != hostname:
                    # This is safe to replace at this point.
                    # The user changed the wrong hostname key, we will move
                    # it to the right one now.
                    if hostname == uuid:
                        key_and_value["host_hostname"] = value

                continue
            key_and_value[key] = value

        if not skip:
            # Set jailed=off and move the jailed dataset.
            checkoutput(["zfs", "set", "jailed=off",
                         "{}/root/data".format(dataset)], stderr=PIPE)
            checkoutput(["zfs", "rename", "-f",
                         "{}/root/data".format(dataset),
                         "{}/data".format(dataset)], stderr=PIPE)
            checkoutput(["zfs", "set",
                         "{}=iocage/jails/{}/data".format(
                             jail_zfs_prop, uuid),
                         "{}/data".format(dataset)], stderr=PIPE)
            checkoutput(["zfs", "set", "jailed=on",
                         "{}/data".format(dataset)], stderr=PIPE)

        key_and_value["jail_zfs_dataset"] = "iocage/jails/{}/data".format(uuid)

        self.json_write(key_and_value)

    def json_load(self):
        """Load the JSON at the location given. Returns a JSON object."""
        version = self.json_get_version()
        skip = False

        try:
            with open(self.location + "/config.json", "r") as conf:
                conf = json.load(conf)
        except FileNotFoundError:
            if path.isfile(self.location + "/config"):
                self.json_convert_from_ucl()

                with open(self.location + "/config.json", "r") as conf:
                    conf = json.load(conf)
            else:
                try:
                    dataset = self.location.split("/")

                    for d in dataset:
                        if len(d) == 36:
                            uuid = d
                        elif len(d) == 8:
                            # Hack88 migration to a perm short UUID.
                            pool, iocroot = _get_pool_and_iocroot()
                            from iocage.lib.ioc_list import IOCList

                            full_uuid = checkoutput(
                                ["zfs", "get", "-H", "-o",
                                 "value",
                                 "org.freebsd.iocage:host_hostuuid",
                                 self.location]).rstrip()
                            jail_hostname = checkoutput(
                                ["zfs", "get", "-H", "-o",
                                 "value",
                                 "org.freebsd.iocage:host_hostname",
                                 self.location]).rstrip()
                            short_uuid = full_uuid[:8]
                            full_dataset = "{}/iocage/jails/{}".format(
                                pool, full_uuid)
                            short_dataset = "{}/iocage/jails/{}".format(
                                pool, short_uuid)

                            self.json_convert_from_zfs(full_uuid)
                            with open(self.location + "/config.json",
                                      "r") as conf:
                                conf = json.load(conf)

                            self.lgr.info("hack88 is no longer supported."
                                          "\n{} is being converted to {} "
                                          "permanently.".format(full_dataset,
                                                                short_dataset))

                            status, _ = IOCList().list_get_jid(full_uuid)
                            if status:
                                self.lgr.info(
                                    "Stopping jail to migrate UUIDs.")
                                from iocage.lib.ioc_stop import IOCStop
                                IOCStop(full_uuid, conf["tag"], self.location,
                                        conf, silent=True)

                            jail_zfs_prop = \
                                "org.freebsd.iocage:jail_zfs_dataset"
                            uuid_prop = "org.freebsd.iocage:host_hostuuid"
                            host_prop = "org.freebsd.iocage:host_hostname"

                            # Set jailed=off and move the jailed dataset.
                            checkoutput(["zfs", "set", "jailed=off",
                                         "{}/data".format(full_dataset)])

                            # We don't want to change a real hostname.
                            if jail_hostname == full_uuid:
                                checkoutput(["zfs", "set", "{}={}".format(
                                    host_prop, short_uuid), full_dataset])

                            checkoutput(["zfs", "set", "{}={}".format(
                                uuid_prop, short_uuid), full_dataset])
                            checkoutput(["zfs", "set",
                                         "{}=iocage/jails/{}/data".format(
                                             jail_zfs_prop, short_uuid),
                                         "{}/data".format(full_dataset)])
                            checkoutput(["zfs", "rename", "-f", full_dataset,
                                         short_dataset])
                            checkoutput(["zfs", "set", "jailed=on",
                                         "{}/data".format(short_dataset)])

                            uuid = short_uuid
                            self.location = "{}/jails/{}".format(iocroot,
                                                                 short_uuid)
                            skip = True

                    self.json_convert_from_zfs(uuid, skip=skip)

                    with open(self.location + "/config.json", "r") as conf:
                        conf = json.load(conf)
                except CalledProcessError:
                    # At this point it should be a real misconfigured jail
                    raise RuntimeError("Configuration is missing!"
                                       f" Please destroy {uuid} and recreate"
                                       " it.")

        try:
            conf_version = conf["CONFIG_VERSION"]

            if version != conf_version:
                conf = self.json_check_config(conf, version)
        except KeyError:
            conf = self.json_check_config(conf, version)

        return conf

    def json_write(self, data, _file="/config.json"):
        """Write a JSON file at the location given with supplied data."""
        with open_atomic(self.location + _file, 'w') as out:
            json.dump(data, out, sort_keys=True, indent=4,
                      ensure_ascii=False)

    def json_get_value(self, prop):
        """Returns a string with the specified prop's value."""
        old = False

        if prop == "pool":
            match = 0
            zpools = Popen(["zpool", "list", "-H", "-o", "name"],
                           stdout=PIPE).communicate()[0].decode(
                "utf-8").split()

            for zfs in zpools:
                dataset = Popen(["zfs", "get", "-H", "-o", "value",
                                 "org.freebsd.ioc:active", zfs],
                                stdout=PIPE).communicate()[0].decode(
                    "utf-8").strip()

                old_dataset = Popen(["zpool", "get", "-H", "-o", "value",
                                     "comment", zfs],
                                    stdout=PIPE).communicate()[0].decode(
                    "utf-8").strip()

                if dataset == "yes":
                    _dataset = zfs
                    match += 1
                elif old_dataset == "iocage":
                    _dataset = zfs
                    match += 1
                    old = True

            if match == 1:
                pool = _dataset

                if old:
                    if os.geteuid() != 0:
                        raise RuntimeError("Run as root to migrate old pool"
                                           " activation property!")
                    check_call(["zpool", "set", "comment=-", pool],
                               stderr=PIPE, stdout=PIPE)
                    check_call(["zfs", "set", "org.freebsd.ioc:active=yes",
                                pool], stderr=PIPE, stdout=PIPE)

                return pool
            elif match >= 2:
                if "deactivate" not in sys.argv[1:]:
                    self.lgr.error("Pools:")
                    for zpool in zpools:
                        self.lgr.error("  {}".format(zpool))
                    raise RuntimeError("You have {} ".format(match) +
                                       "pools marked active for iocage "
                                       "usage.\n"
                                       "Run \"iocage deactivate ZPOOL\" on"
                                       " {} of the".format(match - 1) +
                                       " pools.\n")
            else:
                if len(sys.argv) >= 2 and "activate" in sys.argv[1:]:
                    pass
                else:
                    # We use the first zpool the user has, they are free to
                    # change it.
                    cmd = ["zpool", "list", "-H", "-o", "name"]
                    zpools = Popen(cmd, stdout=PIPE).communicate()[0].decode(
                        "utf-8").split()

                    zpool = zpools[0]

                    if os.geteuid() != 0:
                        raise RuntimeError("Run as root to automatically "
                                           "activate the first zpool!")

                    if zpool == "freenas-boot":
                        try:
                            zpool = zpools[1]
                        except IndexError:
                            raise RuntimeError("Please specify a pool to "
                                               "activate with iocage activate "
                                               "POOL")

                    self.lgr.info(f"Setting up zpool [{zpool}] for"
                                  " iocage usage\n If you wish to change"
                                  " please use \"iocage activate\"")

                    Popen(["zfs", "set", "org.freebsd.ioc:active=yes",
                           zpool]).communicate()

                    return zpool
        elif prop == "iocroot":
            # Location in this case is actually the zpool.
            try:
                loc = "{}/iocage".format(self.location)
                mount = checkoutput(["zfs", "get", "-H", "-o", "value",
                                     "mountpoint", loc]).strip()

                if mount != "none":
                    return mount
                else:
                    raise RuntimeError(f"Please set a mountpoint on {loc}")
            except CalledProcessError:
                raise RuntimeError("{} not found!".format(self.location))
        elif prop == "all":
            conf = self.json_load()

            return conf
        else:
            conf = self.json_load()

            if prop == "last_started" and conf[prop] == "none":
                return "never"
            else:
                return conf[prop]

    def json_set_value(self, prop, create_func=False):
        """Set a property for the specified jail."""
        # Circular dep! Meh.
        from iocage.lib.ioc_list import IOCList
        from iocage.lib.ioc_create import IOCCreate
        key, _, value = prop.partition("=")

        conf = self.json_load()
        old_tag = conf["tag"]
        uuid = conf["host_hostuuid"]
        status, jid = IOCList.list_get_jid(uuid)
        conf[key] = value
        sysctls_cmd = ["sysctl", "-d", "security.jail.param"]
        jail_param_regex = re.compile("security.jail.param.")
        sysctls_list = Popen(sysctls_cmd, stdout=PIPE).communicate()[0].decode(
            "utf-8").split()
        jail_params = [p.replace("security.jail.param.", "").replace(":", "")
                       for p in sysctls_list if re.match(jail_param_regex, p)]
        single_period = ["allow_raw_sockets", "allow_socket_af",
                         "allow_set_hostname"]

        if not create_func:
            if key == "tag":
                conf["tag"] = IOCCreate("", prop, 0).create_link(
                    conf["host_hostuuid"], value, old_tag=old_tag)
                tag = conf["tag"]

        if key == "template":
            pool, iocroot = _get_pool_and_iocroot()
            old_location = "{}/iocage/jails/{}".format(pool, uuid)
            new_location = "{}/iocage/templates/{}".format(pool, old_tag)

            if status:
                raise RuntimeError(f"{uuid} ({old_tag}) is running.\nPlease"
                                   "stop it first!")

            jails, paths = IOCList("uuid").list_datasets()
            for j in jails:
                _uuid = jails[j]
                _path = f"{paths[j]}/root"
                t_old_path = f"{old_location}/root@{_uuid}"
                t_path = f"{new_location}/root@{_uuid}"

                if _uuid == uuid:
                    continue

                origin = checkoutput(["zfs", "get", "-H", "-o", "value",
                                      "origin", _path]).rstrip()

                if origin == t_old_path or origin == t_path:
                    _status, _ = IOCList.list_get_jid(_uuid)

                    if _status:
                        raise RuntimeError(f"CHILD: {_uuid} ({j}) is"
                                           f" running.\nPlease stop it first!")
            if value == "yes":
                try:
                    checkoutput(["zfs", "rename", "-p", old_location,
                                 new_location], stderr=STDOUT)
                    conf["type"] = "template"

                    self.location = new_location.lstrip(pool).replace(
                        "/iocage", iocroot)
                except CalledProcessError as err:
                    raise RuntimeError("{}".format(
                        err.output.decode("utf-8").rstrip()))

                self.lgr.info("{} ({}) converted to a template.".format(uuid,
                                                                        old_tag))
                self.lgr.disabled = True
            elif value == "no":
                try:
                    checkoutput(["zfs", "rename", "-p", new_location,
                                 old_location], stderr=STDOUT)
                    conf["type"] = "jail"

                    self.location = old_location.lstrip(pool).replace(
                        "/iocage", iocroot)
                except CalledProcessError as err:
                    raise RuntimeError("{}".format(
                        err.output.decode("utf-8").rstrip()))

                self.lgr.info("{} ({}) converted to a jail.".format(uuid,
                                                                    old_tag))
                self.lgr.disabled = True

        self.json_check_prop(key, value, conf)
        self.json_write(conf)
        self.lgr.info(
            "Property: {} has been updated to {}".format(key, value))

        # Used for import
        if not create_func:
            if key == "tag":
                return tag

        # We can attempt to set a property in realtime to jail.
        if status:
            if key in single_period:
                key = key.replace("_", ".", 1)
            else:
                key = key.replace("_", ".")

            if key in jail_params:
                try:
                    checkoutput(["jail", "-m", "jid={}".format(jid),
                                 "{}={}".format(key, value)], stderr=STDOUT)
                except CalledProcessError as err:
                    raise RuntimeError("{}".format(
                        err.output.decode("utf-8").rstrip()))

    @staticmethod
    def json_get_version():
        """Sets the iocage configuration version."""
        version = "5"
        return version

    def json_check_config(self, conf, version):
        """
        Takes JSON as input and checks to see what is missing and adds the
        new keys with their default values if missing.
        """
        if geteuid() != 0:
            raise RuntimeError("You need to be root to convert the"
                               " configurations to the new format!")

        _, iocroot = _get_pool_and_iocroot()

        # Version 2 keys
        try:
            sysvmsg = conf["sysvmsg"]
            sysvsem = conf["sysvsem"]
            sysvshm = conf["sysvshm"]
        except KeyError:
            sysvmsg = "new"
            sysvsem = "new"
            sysvshm = "new"

        # Set all keys, even if it's the same value.
        conf["sysvmsg"] = sysvmsg
        conf["sysvsem"] = sysvsem
        conf["sysvshm"] = sysvshm

        # Version 3 keys
        try:
            release = conf["release"]
            cloned_release = conf["cloned_release"]
        except KeyError:
            try:
                freebsd_version = f"{iocroot}/releases/{conf['release']}" \
                                  "/root/bin/freebsd-version"
            except (IOError, OSError):
                freebsd_version = f"{iocroot}/templates/{conf['tag']}" \
                                  "/root/bin/freebsd-version"

            if conf["release"][:4].endswith("-"):
                # 9.3-RELEASE and under don't actually have this binary.
                release = conf["release"]
            else:
                with open(freebsd_version, "r") as r:
                    for line in r:
                        if line.startswith("USERLAND_VERSION"):
                            release = line.rstrip().partition("=")[2].strip(
                                '"')

            cloned_release = conf["release"]

        # Set all Version 3 keys
        conf["release"] = release
        conf["cloned_release"] = cloned_release

        # Version 4 keys
        try:
            basejail = conf["basejail"]
        except KeyError:
            basejail = "no"

        # Set all keys, even if it's the same value.
        conf["basejail"] = basejail

        # Version 5 keys
        try:
            comment = conf["comment"]
        except KeyError:
            comment = "none"

        # Set all keys, even if it's the same value.
        conf["comment"] = comment

        conf["CONFIG_VERSION"] = version
        self.json_write(conf)

        return conf

    def json_check_prop(self, key, value, conf):
        """
        Checks if the property matches known good values, if it's the
        CLI, deny setting any properties not in this list.
        """
        props = {
            # Network properties
            "interfaces"           : (":", ","),
            "host_domainname"      : ("string",),
            "host_hostname"        : ("string",),
            "exec_fib"             : ("string",),
            "ip4_addr"             : ("|",),
            "ip4_saddrsel"         : ("0", "1",),
            "ip4"                  : ("new", "inherit", "none"),
            "ip6_addr"             : ("|",),
            "ip6_saddrsel"         : ("0", "1"),
            "ip6"                  : ("new", "inherit", "none"),
            "defaultrouter"        : ("string",),
            "defaultrouter6"       : ("string",),
            "resolver"             : ("string",),
            "mac_prefix"           : ("string",),
            "vnet0_mac"            : ("string",),
            "vnet1_mac"            : ("string",),
            "vnet2_mac"            : ("string",),
            "vnet3_mac"            : ("string",),
            # Jail Properties
            "devfs_ruleset"        : ("string",),
            "exec_start"           : ("string",),
            "exec_stop"            : ("string",),
            "exec_prestart"        : ("string",),
            "exec_poststart"       : ("string",),
            "exec_prestop"         : ("string",),
            "exec_poststop"        : ("string",),
            "exec_clean"           : ("0", "1"),
            "exec_timeout"         : ("string",),
            "stop_timeout"         : ("string",),
            "exec_jail_user"       : ("string",),
            "exec_system_jail_user": ("string",),
            "exec_system_user"     : ("string",),
            "mount_devfs"          : ("0", "1"),
            "mount_fdescfs"        : ("0", "1"),
            "enforce_statfs"       : ("0", "1", "2"),
            "children_max"         : ("string",),
            "login_flags"          : ("string",),
            "securelevel"          : ("string",),
            "sysvmsg"              : ("new", "inherit", "disable"),
            "sysvsem"              : ("new", "inherit", "disable"),
            "sysvshm"              : ("new", "inherit", "disable"),
            "allow_set_hostname"   : ("0", "1"),
            "allow_sysvipc"        : ("0", "1"),
            "allow_raw_sockets"    : ("0", "1"),
            "allow_chflags"        : ("0", "1"),
            "allow_mount"          : ("0", "1"),
            "allow_mount_devfs"    : ("0", "1"),
            "allow_mount_nullfs"   : ("0", "1"),
            "allow_mount_procfs"   : ("0", "1"),
            "allow_mount_tmpfs"    : ("0", "1"),
            "allow_mount_zfs"      : ("0", "1"),
            "allow_quotas"         : ("0", "1"),
            "allow_socket_af"      : ("0", "1"),
            # RCTL limits
            "cpuset"               : ("off", "on"),
            "rlimits"              : ("off", "on"),
            "memoryuse"            : ":",
            "memorylocked"         : ("off", "on"),
            "vmemoryuse"           : ("off", "on"),
            "maxproc"              : ("off", "on"),
            "cputime"              : ("off", "on"),
            "pcpu"                 : ":",
            "datasize"             : ("off", "on"),
            "stacksize"            : ("off", "on"),
            "coredumpsize"         : ("off", "on"),
            "openfiles"            : ("off", "on"),
            "pseudoterminals"      : ("off", "on"),
            "swapuse"              : ("off", "on"),
            "nthr"                 : ("off", "on"),
            "msgqqueued"           : ("off", "on"),
            "msgqsize"             : ("off", "on"),
            "nmsgq"                : ("off", "on"),
            "nsemop"               : ("off", "on"),
            "nshm"                 : ("off", "on"),
            "shmsize"              : ("off", "on"),
            "wallclock"            : ("off", "on"),
            # Custom properties
            "tag"                  : ("string",),
            "bpf"                  : ("off", "on"),
            "dhcp"                 : ("off", "on"),
            "boot"                 : ("off", "on"),
            "notes"                : ("string",),
            "owner"                : ("string",),
            "priority"             : str(tuple(range(1, 100))),
            "hostid"               : ("string",),
            "jail_zfs"             : ("off", "on"),
            "jail_zfs_dataset"     : ("string",),
            "jail_zfs_mountpoint"  : ("string",),
            "mount_procfs"         : ("0", "1"),
            "mount_linprocfs"      : ("0", "1"),
            "vnet"                 : ("off", "on"),
            "template"             : ("no", "yes"),
            "comment"              : ("string",)
        }

        zfs_props = {
            # ZFS Props
            "compression"  : "lz4",
            "origin"       : "readonly",
            "quota"        : "none",
            "mountpoint"   : "readonly",
            "compressratio": "readonly",
            "available"    : "readonly",
            "used"         : "readonly",
            "dedup"        : "off",
            "reservation"  : "none",
        }

        if key in zfs_props.keys():
            pool, _ = _get_pool_and_iocroot()

            if conf["template"] == "yes":
                _type = "templates"
                uuid = conf["tag"]  # I know, but it's easier this way.
            else:
                _type = "jails"
                uuid = conf["host_hostuuid"]

            if key == "quota":
                if value != "none" and not value.upper().endswith(("M", "G",
                                                                   "T")):
                    err = f"{value} should have a suffix ending in" \
                          " M, G, or T."
                    raise RuntimeError(err)

            checkoutput(["zfs", "set", f"{key}={value}",
                         f"{pool}/iocage/{_type}/{uuid}"])
            return

        if key in props.keys():
            # Either it contains what we expect, or it's a string.
            for k in props[key]:
                if k in value:
                    return

            if props[key][0] == "string":
                return
            else:
                err = f"{value} is not a valid value for {key}.\n"

                if self.cli:
                    self.lgr.error(f"{err}")
                else:
                    err = f"{err}"

                if key not in ("interfaces", "ip4_addr", "ip6_addr",
                               "memoryuse"):
                    msg = f"Value must be {' or '.join(props[key])}"

                    if not self.cli:
                        msg = err + msg

                    raise RuntimeError(msg)
                elif key == "ip4_addr":
                    msg = "IP address must contain both an interface and IP " \
                          "address.\nEXAMPLE: em0|192.168.1.10"

                    if not self.cli:
                        msg = err + msg

                    raise RuntimeError(msg)
                elif key == "ip6_addr":
                    msg = "IP address must contain both an interface and IP " \
                          "address.\nEXAMPLE: em0|fe80::5400:ff:fe54:1"

                    if not self.cli:
                        msg = err + msg

                    raise RuntimeError(msg)
                elif key == "interfaces":
                    msg = "Interfaces must be specified as a pair.\n" \
                          "EXAMPLE: vnet0:bridge0, vnet1:bridge1"

                    if not self.cli:
                        msg = err + msg

                    raise RuntimeError(msg)
                elif key == "memoryuse":
                    msg = "memoryuse requires at minimum a pair.\nEXAMPLE: " \
                          "8g:log"

                    if not self.cli:
                        msg = err + msg

                    raise RuntimeError(msg)
                else:
                    if self.cli:
                        exit(1)
        else:
            if self.cli:
                raise RuntimeError(
                    f"{key} cannot be changed by the user.")
            else:
                if key not in conf.keys():
                    raise RuntimeError(
                        f"{key} is not a valid property!")

    def json_plugin_load(self):
        try:
            with open("{}/plugin/settings.json".format(
                    self.location), "r") as settings:
                settings = json.load(settings)
        except (IOError, OSError):
            raise RuntimeError(
                "No settings.json exists in {}/plugin!".format(self.location))

        return settings

    def json_plugin_get_value(self, prop):
        from iocage.lib.ioc_exec import IOCExec

        pool, iocroot = _get_pool_and_iocroot()
        conf = self.json_load()
        uuid = conf["host_hostuuid"]
        tag = conf["tag"]
        _path = checkoutput(["zfs", "get", "-H", "-o", "value", "mountpoint",
                             "{}/iocage/jails/{}".format(pool,
                                                         uuid)]).rstrip()
        # Plugin variables
        settings = self.json_plugin_load()
        serviceget = settings["serviceget"]
        prop_error = ".".join(prop)

        if "options" in prop:
            _prop = prop[1:]
        else:
            _prop = prop

        prop_cmd = "{},{}".format(serviceget, ",".join(_prop)).split(",")
        try:
            if prop[0] != "all":
                if len(_prop) > 1:
                    return get_nested_key(settings, prop)
                else:
                    return IOCExec(prop_cmd, uuid, tag, _path).exec_jail()
            else:
                return settings
        except KeyError:
            raise RuntimeError(
                "Key: \"{}\" does not exist!".format(prop_error))

    def json_plugin_set_value(self, prop):
        from iocage.lib.ioc_exec import IOCExec
        from iocage.lib.ioc_list import IOCList

        pool, iocroot = _get_pool_and_iocroot()
        conf = self.json_load()
        uuid = conf["host_hostuuid"]
        tag = conf["tag"]
        _path = checkoutput(["zfs", "get", "-H", "-o", "value", "mountpoint",
                             "{}/iocage/jails/{}".format(pool,
                                                         uuid)]).rstrip()
        status, _ = IOCList().list_get_jid(uuid)

        # Plugin variables
        settings = self.json_plugin_load()
        serviceset = settings["serviceset"]
        servicerestart = settings["servicerestart"].split()
        keys, _, value = ".".join(prop).partition("=")
        prop = keys.split(".")
        restart = False

        if "options" in prop:
            prop = keys.split(".")[1:]

        prop_cmd = "{},{},{}".format(serviceset, ",".join(prop), value).split(
            ",")
        setting = settings["options"]

        try:
            while prop:
                current = prop[0]
                key = current
                prop.remove(current)

                if not prop:
                    if setting[current]:
                        try:
                            restart = setting[current]["requirerestart"]
                        except KeyError:
                            pass
                else:
                    setting = setting[current]

            if status:
                # IOCExec will not show this if it doesn't start the jail.
                self.lgr.info("Command output:")
            IOCExec(prop_cmd, uuid, tag, _path).exec_jail()

            if restart:
                self.lgr.info("\n-- Restarting service --")
                self.lgr.info("Command output:")
                IOCExec(servicerestart, uuid, tag, _path).exec_jail()

            self.lgr.info("\nKey: {} has been updated to {}".format(keys,
                                                                    value))
        except KeyError:
            raise RuntimeError("Key: \"{}\" does not exist!".format(key))
