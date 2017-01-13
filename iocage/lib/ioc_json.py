"""Convert, load or write JSON."""
import json
import logging
import sys
from subprocess import CalledProcessError, PIPE, Popen, check_output

import re
from os import geteuid, path


def _get_pool_and_iocroot():
    """For internal setting of pool and iocroot."""
    pool = IOCJson("").get_prop_value("pool")
    iocroot = IOCJson(pool).get_prop_value("iocroot")

    return (pool, iocroot)


class IOCJson(object):
    """
    Migrates old iocage configurations(UCL and ZFS Props) to the new JSON
    format, will set and get properties.
    """

    def __init__(self, location, silent=False):
        self.location = location
        self.lgr = logging.getLogger('ioc_json')

        if silent:
            self.lgr.disabled = True

    @staticmethod
    def convert_to_json_ucl():
        """Convert to JSON. Accepts a location to the ucl configuration."""
        raise RuntimeError("Migrating from iocage develop is not supported!")
        # Maybe one day, but today is not that day.
        # if geteuid() != 0:
        #     raise RuntimeError("You need to be root to convert the"
        #                        " configuration to the new format!")
        #
        # with open(self.location + "/config") as conf:
        #     lines = conf.readlines()
        #
        # key_and_value = {}
        #
        # for line in lines:
        #     line = line.partition("=")
        #     key = line[0].rstrip()
        #     value = line[2].replace(";", "").replace('"', '').strip()
        #
        #     key_and_value[key] = value
        #
        # self.write_json(key_and_value)

    def convert_to_json_zfs(self, uuid):
        """Convert to JSON. Accepts a jail UUID"""
        pool, iocroot = _get_pool_and_iocroot()

        if geteuid() != 0:
            raise RuntimeError("You need to be root to convert the"
                               " configuration to the new format!")

        cmd = ["zfs", "get", "-H", "-s", "local", "-o", "property,value",
               "all", "{}{}/jails/{}".format(pool, iocroot, uuid)]

        regex = re.compile("org.freebsd.iocage")

        zfs_get = Popen(cmd, stdout=PIPE).communicate()[0].split("\n")

        # Find each of the props we want to convert.
        props = [p for p in zfs_get if re.search(regex, p)]

        key_and_value = {"host_domainname": "none",
                         "CONFIG_VERSION" : self.iocage_version()
                         }

        for prop in props:
            prop = prop.partition(":")
            key = prop[2].split("\t")[0]
            value = prop[2].split("\t")[1].strip()

            if key == "type":
                if value == "basejail":
                    # These were just clones on master.
                    value = "jail"
            key_and_value[key] = value

        self.write_json(key_and_value)

    def load_json(self):
        """Load the JSON at the location given. Returns a JSON object."""
        try:
            with open(self.location + "/config.json") as conf:
                conf = json.load(conf)
                self.check_config(conf)
        except IOError:
            if path.isfile(self.location + "/config"):
                self.convert_to_json_ucl()

                with open(self.location + "/config.json") as conf:
                    conf = json.load(conf)
            else:
                uuid = self.location.split("/")[3]
                self.convert_to_json_zfs(uuid)

                with open(self.location + "/config.json") as conf:
                    conf = json.load(conf)

        return conf

    def write_json(self, data):
        """Write a JSON file at the location given with supplied data."""
        with open(self.location + "/config.json", 'w') as out:
            json.dump(data, out, sort_keys=True, indent=4,
                      ensure_ascii=False)

    def get_prop_value(self, prop):
        """Returns a string with the specified prop's value."""
        if prop == "pool":
            match = 0
            # zpools = Popen(["zpool", "list", "-H", "-o", "name"], stdout=PIPE)
            zpools = Popen(["zpool", "list", "-H", "-o", "name"],
                           stdout=PIPE).communicate()[0].split()

            for zfs in zpools:
                dataset = Popen(["zfs", "get", "-H", "-o", "value",
                                 "org.freebsd.ioc:active", zfs],
                                stdout=PIPE).communicate()[0].strip()

                if dataset == "yes":
                    _dataset = zfs
                    match += 1

            if match == 1:
                pool = _dataset

                return pool
            elif match >= 2:
                if "deactivate" not in sys.argv[1:]:
                    raise RuntimeError("You have {} ".format(match) +
                                       "pools marked active for iocage usage.\n"
                                       "Run \"ioc deactivate ZPOOL\" on"
                                       " {} of the".format(match - 1) +
                                       " pools.\n")
            else:
                if len(sys.argv) >= 2 and "activate" in sys.argv[1:]:
                    pass
                else:
                    raise RuntimeError("No pools are marked active for iocage"
                                       " usage.\nRun \"iocage activate\" on a"
                                       " zpool.")
        elif prop == "iocroot":
            # Location in this case is actually the zpool.
            try:
                loc = "{}/iocage".format(self.location)
                mount = check_output(["zfs", "get", "-H", "-o", "value",
                                      "mountpoint", loc]).strip()

                # Happens if the user has iocage-develop installed
                # concurrently.
                if mount == "/{}/iocage".format(self.location):
                    mount = "/iocage"

                return mount
            except CalledProcessError:
                raise RuntimeError("{} not found!".format(self.location))
        else:
            conf = self.load_json()

            if prop == "last_started" and conf[prop] == "none":
                return "never"
            else:
                return conf[prop]

    def set_prop_value(self, prop, create_func=False):
        """Set a property for the specified jail."""
        key, _, value = prop.partition("=")

        conf = self.load_json()
        old_tag = conf["tag"]
        conf[key] = value

        if not create_func:
            if key == "tag":
                # Circular dep! Meh.
                from iocage.lib.ioc_create import IOCCreate
                conf["tag"] = IOCCreate("", prop, 0).create_link(
                        conf["host_hostuuid"], value, old_tag=old_tag)
                tag = conf["tag"]
        self.write_json(conf)

        self.lgr.info(
                "Property: {} has been updated to {}".format(key, value))

        # Used for import
        if not create_func:
            if key == "tag":
                return tag

    @staticmethod
    def iocage_version():
        """Sets the iocage configuration version."""
        version = "1"
        return version

    def check_config(self, conf):
        """
        Takes JSON as input and checks the config version and adds any keys
        and their default values that don't exist.
        """
        version = self.iocage_version()
        conf_version = conf["CONFIG_VERSION"]

        if version != conf_version:
            # TODO: When we have a real change to keys to migrate.
            conf["CONFIG_VERSION"] = version
            self.write_json(conf)
