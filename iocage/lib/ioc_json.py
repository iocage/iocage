"""Convert, load or write JSON."""
import json
import logging
import os
import re
import subprocess as su
import sys
import libzfs

import iocage.lib.ioc_common
import iocage.lib.ioc_create
import iocage.lib.ioc_exec
import iocage.lib.ioc_list
import iocage.lib.ioc_stop


def _get_pool_and_iocroot():
    """For internal setting of pool and iocroot."""
    pool = IOCJson().json_get_value("pool")
    iocroot = IOCJson(pool).json_get_value("iocroot")

    return pool, iocroot


class IOCJson(object):
    """
    Migrates old iocage configurations(UCL and ZFS Props) to the new JSON
    format, will set and get properties.
    """

    def __init__(self, location="", silent=False, cli=False, callback=None):
        self.location = location
        self.lgr = logging.getLogger('ioc_json')
        self.cli = cli
        self.silent = silent
        self.callback = callback
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

    def json_convert_from_ucl(self):
        """Convert to JSON. Accepts a location to the ucl configuration."""
        if os.geteuid() != 0:
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
        dataset = f"{pool}/iocage/jails/{uuid}"
        jail_zfs_prop = "org.freebsd.iocage:jail_zfs_dataset"

        if os.geteuid() != 0:
            raise RuntimeError("You need to be root to convert the"
                               " configurations to the new format!")

        props = self.zfs.get_dataset(dataset).properties

        # Filter the props we want to convert.
        prop_prefix = "org.freebsd.iocage"
        props = list(filter(lambda x: x.startswith("org.freebsd.iocage")))

        key_and_value = {"host_domainname": "none"}

        for prop, value in props:
            key = prop.partition(":")[2]

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
            self.zfs_set_property(f"{dataset}/root/data", "jailed", "off")
            self.zfs.get_dataset(f"{dataset}/root/data").rename(f"{dataset}/data")
            self.zfs_set_property(f"{dataset}/data", jail_zfs_prop, f"iocage/jails/{uuid}/data")
            self.zfs_set_property(f"{dataset}/data", "jailed", "on")

        key_and_value["jail_zfs_dataset"] = f"iocage/jails/{uuid}/data"

        self.json_write(key_and_value)

    def _zfs_get_properties(self, identifier):
        if "/" in identifier:
            dataset = self.zfs.get_dataset(identifier)
            return dataset.properties
        else:
            pool = self.zfs.get(identifier)
            return pool.root_dataset.properties

    def zfs_get_property(self, identifier, key):
        try:
            return self._zfs_get_properties(identifier)[key].value
        except:
            return ""

    def zfs_set_property(self, identifier, key, value):
        if ":" in key:
            newproperty = libzfs.ZFSUserProperty(value)
        else:
            newproperty = libzfs.ZFSProperty(value)

        self._zfs_get_properties(identifier)[key] = newproperty;

    def json_load(self):
        """Load the JSON at the location given. Returns a JSON object."""
        version = self.json_get_version()
        skip = False

        try:
            with open(self.location + "/config.json", "r") as conf:
                conf = json.load(conf)
        except FileNotFoundError:
            if os.path.isfile(self.location + "/config"):
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

                            full_uuid = self.zfs_get_property(self.location, 'org.freebsd.iocage:host_hostuuid')
                            jail_hostname = self.zfs_get_property(self.location, 'org.freebsd.iocage:host_hostname')
                            short_uuid = full_uuid[:8]
                            full_dataset = f"{pool}/iocage/jails/{full_uuid}"
                            short_dataset = f"{pool}/iocage/jails/{short_uuid}"

                            self.json_convert_from_zfs(full_uuid)
                            with open(self.location + "/config.json",
                                      "r") as conf:
                                conf = json.load(conf)

                            iocage.lib.ioc_common.logit({
                                "level"  : "INFO",
                                "message": "hack88 is no longer supported."
                                           f"\n{full_dataset} is being "
                                           f"converted to {short_dataset}"
                                           f" permanently."
                            },
                                _callback=self.callback,
                                silent=self.silent)

                            status, _ = iocage.lib.ioc_list.IOCList(

                            ).list_get_jid(
                                full_uuid)
                            if status:
                                iocage.lib.ioc_common.logit({
                                    "level"  : "INFO",
                                    "message":
                                        "Stopping jail to migrate UUIDs."
                                },
                                    _callback=self.callback,
                                    silent=self.silent)
                                iocage.lib.ioc_stop.IOCStop(full_uuid,
                                                            conf["tag"],
                                                            self.location,
                                                            conf, silent=True)

                            jail_zfs_prop = \
                                "org.freebsd.iocage:jail_zfs_dataset"
                            uuid_prop = "org.freebsd.iocage:host_hostuuid"
                            host_prop = "org.freebsd.iocage:host_hostname"

                            # Set jailed=off and move the jailed dataset.
                            self.zfs_set_property(f"{full_dataset}/data", 'jailed', 'off')

                            # We don't want to change a real hostname.
                            if jail_hostname == full_uuid:
                                self.zfs_set_property(full_dataset, host_prop, short_uuid)

                            self.zfs_set_property(full_dataset, uuid_prop, short_uuid)
                            self.zfs_set_property(f"{full_dataset}/data", jail_zfs_prop, f"iocage/jails/{short_uuid}/data")

                            self.zfs.get_dataset(full_dataset).rename(short_dataset)
                            self.zfs_set_property(f"{short_dataset}/data", "jailed", "on")

                            uuid = short_uuid
                            self.location = f"{iocroot}/jails/{short_uuid}"
                            skip = True

                    self.json_convert_from_zfs(uuid, skip=skip)

                    with open(self.location + "/config.json", "r") as conf:
                        conf = json.load(conf)
                except su.CalledProcessError:
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
        with iocage.lib.ioc_common.open_atomic(self.location + _file,
                                               'w') as out:
            json.dump(data, out, sort_keys=True, indent=4,
                      ensure_ascii=False)

    def _upgrade_pool(self, pool):
        if os.geteuid() != 0:
            raise RuntimeError("Run as root to migrate old pool"
                               " activation property!")

        self.zfs_set_property(pool, "org.freebsd.ioc:active", "yes")
        self.zfs_set_property(pool, "comment", "-")


    def json_get_value(self, prop):
        """Returns a string with the specified prop's value."""
        old = False
        zpools = list(map(lambda x: x.name, list(self.zfs.pools)))

        if prop == "pool":
            match = 0

            for pool in zpools:

                prop_ioc_active = self.zfs_get_property(pool, "org.freebsd.ioc:active");
                prop_comment = self.zfs_get_property(pool, "comment")

                if prop_ioc_active == "yes":
                    _dataset = pool
                    match += 1
                elif prop_comment == "iocage":
                    _dataset = pool
                    match += 1
                    old = True

            if match == 1:
                if old:
                    self._upgrade_pool(_dataset)
                return _dataset

            elif match >= 2:
                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": "Pools:"
                },
                    _callback=self.callback,
                    silent=self.silent)
                for zpool in zpools:
                    iocage.lib.ioc_common.logit({
                        "level"  : "ERROR",
                        "message": f"  {zpool}"
                    },
                        _callback=self.callback,
                        silent=self.silent)
                raise RuntimeError(f"You have {match} pools marked active"
                                   " for iocage usage.\n Run \"iocage"
                                   f" activate ZPOOL\" on the preferred"
                                   " pool.\n")
            else:
                if len(sys.argv) >= 2 and "activate" in sys.argv[1:]:
                    pass
                else:
                    # We use the first zpool the user has, they are free to
                    # change it.
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

                    iocage.lib.ioc_common.logit({
                        "level"  : "INFO",
                        "message": f"Setting up zpool [{zpool}] for"
                                   " iocage usage\n If you wish to change"
                                   " please use \"iocage activate\""
                    },
                        _callback=self.callback,
                        silent=self.silent)

                    self.zfs_set_property(zpool, "org.freebsd.ioc:active", "yes")
                    return zpool

        elif prop == "iocroot":
            # Location in this case is actually the zpool.
            try:
                loc = f"{self.location}/iocage"
                mount = self.zfs_get_property(loc, "mountpoint")

                if mount != "none":
                    return mount
                else:
                    raise RuntimeError(f"Please set a mountpoint on {loc}")
            except:
                raise RuntimeError(f"{self.location} not found!")
        elif prop == "all":
            conf = self.json_load()

            return conf
        else:
            conf = self.json_load()

            if prop == "last_started" and conf[prop] == "none":
                return "never"
            else:
                return conf[prop]

    def json_set_value(self, prop, create_func=False, _import=False):
        """Set a property for the specified jail."""
        # Circular dep! Meh.
        key, _, value = prop.partition("=")

        conf = self.json_load()
        old_tag = conf["tag"]
        uuid = conf["host_hostuuid"]
        status, jid = iocage.lib.ioc_list.IOCList.list_get_jid(uuid)
        conf[key] = value
        sysctls_cmd = ["sysctl", "-d", "security.jail.param"]
        jail_param_regex = re.compile("security.jail.param.")
        sysctls_list = su.Popen(sysctls_cmd, stdout=su.PIPE).communicate()[
            0].decode(
            "utf-8").split()
        jail_params = [p.replace("security.jail.param.", "").replace(":", "")
                       for p in sysctls_list if re.match(jail_param_regex, p)]
        single_period = ["allow_raw_sockets", "allow_socket_af",
                         "allow_set_hostname"]

        if not create_func:
            if key == "tag":
                conf["tag"] = iocage.lib.ioc_create.IOCCreate("", prop,
                                                              0).create_link(
                    conf["host_hostuuid"], value, old_tag=old_tag)
                tag = conf["tag"]

        if key == "template":
            pool, iocroot = _get_pool_and_iocroot()
            old_location = f"{pool}/iocage/jails/{uuid}"
            new_location = f"{pool}/iocage/templates/{old_tag}"

            if status:
                raise RuntimeError(f"{uuid} ({old_tag}) is running.\nPlease"
                                   "stop it first!")

            jails, paths = iocage.lib.ioc_list.IOCList("uuid").list_datasets()
            for j in jails:
                _uuid = jails[j]
                _path = f"{paths[j]}/root"
                t_old_path = f"{old_location}/root@{_uuid}"
                t_path = f"{new_location}/root@{_uuid}"

                if _uuid == uuid:
                    continue

                origin = self.zfs_get_property(_path, 'origin')

                if origin == t_old_path or origin == t_path:
                    _status, _ = iocage.lib.ioc_list.IOCList.list_get_jid(
                        _uuid)

                    if _status:
                        raise RuntimeError(f"CHILD: {_uuid} ({j}) is"
                                           f" running.\nPlease stop it first!")
            if value == "yes":
                self.zfs.get_dataset(old_location).rename(new_location)
                conf["type"] = "template"

                self.location = new_location.lstrip(pool).replace("/iocage", iocroot)

                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"{uuid} ({old_tag}) converted to a template."
                },
                    _callback=self.callback,
                    silent=self.silent)
                self.lgr.disabled = True
            elif value == "no":
                if not _import:
                    self.zfs.get_dataset(old_location).rename(new_location)
                    conf["type"] = "jail"
                    self.location = old_location.lstrip(pool).replace("/iocage", iocroot)

                    iocage.lib.ioc_common.logit({
                        "level"  : "INFO",
                        "message": f"{uuid} ({old_tag}) converted to a jail."
                    },
                        _callback=self.callback,
                        silent=self.silent)
                    self.lgr.disabled = True

        self.json_check_prop(key, value, conf)
        self.json_write(conf)
        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message":
                f"Property: {key} has been updated to {value}"
        },
            _callback=self.callback,
            silent=self.silent)

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
                if conf["vnet"] == "on" and key == "ip4.addr" or key == \
                        "ip6.addr":
                    return
                try:
                    iocage.lib.ioc_common.checkoutput(
                        ["jail", "-m", f"jid={jid}",
                         f"{key}={value}"],
                        stderr=su.STDOUT)
                except su.CalledProcessError as err:
                    raise RuntimeError(
                        f"{err.output.decode('utf-8').rstrip()}")

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
        if os.geteuid() != 0:
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
            except FileNotFoundError:
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

            self.zfs_set_property(f"{pool}/iocage/{_type}/{uuid}", key, value)

        elif key in props.keys():
            # Either it contains what we expect, or it's a string.
            for k in props[key]:
                if k in value:
                    return

            if props[key][0] == "string":
                return
            else:
                if key == "ip4_addr" or key == "ip6_addr" and value == "none":
                    err = ""
                else:
                    err = f"{value} is not a valid value for {key}.\n"

                if self.cli:
                    iocage.lib.ioc_common.logit({
                        "level"  : "ERROR",
                        "message": f"{err}"
                    },
                        _callback=self.callback,
                        silent=self.silent)
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

                    if value != "none":
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
            with open(f"{self.location}/plugin/settings.json", "r") as \
                    settings:
                settings = json.load(settings)
        except FileNotFoundError:
            raise RuntimeError(
                f"No settings.json exists in {self.location}/plugin!")

        return settings

    def json_plugin_get_value(self, prop):
        pool, iocroot = _get_pool_and_iocroot()
        conf = self.json_load()
        uuid = conf["host_hostuuid"]
        tag = conf["tag"]
        _path = self.zfs_get_property(f"{pool}/iocage/jails/{uuid}", "mountpoint")

        # Plugin variables
        settings = self.json_plugin_load()
        serviceget = settings["serviceget"]
        prop_error = ".".join(prop)

        if "options" in prop:
            _prop = prop[1:]
        else:
            _prop = prop

        prop_cmd = f"{serviceget},{','.join(_prop)}".split(",")
        try:
            if prop[0] != "all":
                if len(_prop) > 1:
                    return iocage.lib.ioc_common.get_nested_key(settings, prop)
                else:
                    return iocage.lib.ioc_exec.IOCExec(prop_cmd, uuid, tag,
                                                       _path).exec_jail()
            else:
                return settings
        except KeyError:
            raise RuntimeError(
                f"Key: \"{prop_error}\" does not exist!")

    def json_plugin_set_value(self, prop):
        pool, iocroot = _get_pool_and_iocroot()
        conf = self.json_load()
        uuid = conf["host_hostuuid"]
        tag = conf["tag"]
        _path = self.zfs_get_property(f"{pool}/iocage/jails/{uuid}", "mountpoint")
        status, _ = iocage.lib.ioc_list.IOCList().list_get_jid(uuid)

        # Plugin variables
        settings = self.json_plugin_load()
        serviceset = settings["serviceset"]
        servicerestart = settings["servicerestart"].split()
        keys, _, value = ".".join(prop).partition("=")
        prop = keys.split(".")
        restart = False
        readonly = False

        if "options" in prop:
            prop = keys.split(".")[1:]

        prop_cmd = f"{serviceset},{','.join(prop)},{value}".split(
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
                            readonly = setting[current]["readonly"]
                        except KeyError:
                            pass
                else:
                    setting = setting[current]

            if readonly:
                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": "This key is readonly!"
                })
                return True

            if status:
                # IOCExec will not show this if it doesn't start the jail.
                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": "Command output:"
                },
                    _callback=self.callback,
                    silent=self.silent)
            iocage.lib.ioc_exec.IOCExec(prop_cmd, uuid, tag, _path).exec_jail()

            if restart:
                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": "\n-- Restarting service --"
                },
                    _callback=self.callback,
                    silent=self.silent)
                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": "Command output:"
                },
                    _callback=self.callback,
                    silent=self.silent)
                iocage.lib.ioc_exec.IOCExec(servicerestart, uuid, tag, _path
                                            ).exec_jail()

            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": f"\nKey: {keys} has been updated to {value}"
            },
                _callback=self.callback,
                silent=self.silent)
        except KeyError:
            raise RuntimeError(f"Key: \"{key}\" does not exist!")
