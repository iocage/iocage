"""Convert, load or write JSON."""
import json
import logging
import os
import re
import sys
from builtins import object
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

    def __init__(self, location="", silent=False):
        self.location = location
        self.lgr = logging.getLogger('ioc_json')

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

    def json_convert_from_zfs(self, uuid):
        """Convert to JSON. Accepts a jail UUID"""
        pool, _ = _get_pool_and_iocroot()

        if geteuid() != 0:
            raise RuntimeError("You need to be root to convert the"
                               " configurations to the new format!")

        cmd = ["zfs", "get", "-H", "-o", "property,value", "all",
               "{}/iocage/jails/{}".format(pool, uuid)]

        regex = re.compile("org.freebsd.iocage")

        zfs_get = Popen(cmd, stdout=PIPE).communicate()[0].split("\n")

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
            key_and_value[key] = value

        self.json_write(key_and_value)

    def json_load(self):
        """Load the JSON at the location given. Returns a JSON object."""
        version = self.json_get_version()

        try:
            with open(self.location + "/config.json", "r") as conf:
                conf = json.load(conf)
        except (IOError, OSError):
            if path.isfile(self.location + "/config"):
                self.json_convert_from_ucl()

                with open(self.location + "/config.json", "r") as conf:
                    conf = json.load(conf)
            else:
                dataset = self.location.split("/")

                for d in dataset:
                    if len(d) == 36:
                        uuid = d

                self.json_convert_from_zfs(uuid)

                with open(self.location + "/config.json", "r") as conf:
                    conf = json.load(conf)

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

                if old_dataset == "iocage":
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
                    raise RuntimeError("You have {} ".format(match) +
                                       "pools marked active for iocage "
                                       "usage.\n"
                                       "Run \"ioc deactivate ZPOOL\" on"
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

                    if os.geteuid() != 0:
                        raise RuntimeError("Run as root to automatically "
                                           "activate the first zpool!")

                    self.lgr.info("Setting up zpool [{}] for iocage usage\n"
                                  "If you wish to change please use "
                                  "\"iocage activate\"".format(zpools[0]))

                    Popen(["zfs", "set", "org.freebsd.ioc:active=yes",
                           zpools[0]]).communicate()

                    return zpools[0]
        elif prop == "iocroot":
            # Location in this case is actually the zpool.
            try:
                loc = "{}/iocage".format(self.location)
                mount = checkoutput(["zfs", "get", "-H", "-o", "value",
                                     "mountpoint", loc]).strip()
                return mount
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
        # TODO: Some value sanitization for any property.
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
                raise RuntimeError("{} ({}) is running."
                                   " Please stop it first!".format(uuid,
                                                                   old_tag))
            if value == "yes":
                try:
                    checkoutput(["zfs", "rename", "-p", old_location,
                                 new_location], stderr=STDOUT)
                    conf["type"] = "template"

                    self.location = new_location.lstrip(pool).replace(
                        "/iocage", iocroot)
                except CalledProcessError as err:
                    raise RuntimeError("ERROR: {}".format(
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
                    raise RuntimeError("ERROR: {}".format(
                        err.output.decode("utf-8").rstrip()))

                self.lgr.info("{} ({}) converted to a jail.".format(uuid,
                                                                    old_tag))
                self.lgr.disabled = True

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
                    raise RuntimeError("ERROR: {}".format(
                        err.output.decode("utf-8").rstrip()))

    @staticmethod
    def json_get_version():
        """Sets the iocage configuration version."""
        version = "3"
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
            freebsd_version = "{}/releases/{}/root/bin/freebsd-version".format(
                iocroot, conf["release"])
        except (IOError, OSError):
            freebsd_version = "{}/templates/{" \
                              "}/root/bin/freebsd-version".format(
                iocroot, conf["tag"])

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

        conf["CONFIG_VERSION"] = version
        self.json_write(conf)

        return conf

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
                            restart = False
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
