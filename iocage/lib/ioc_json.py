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
"""Convert, load or write JSON."""
import collections
import datetime
import fileinput
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

    def __init__(self, location="", silent=False, cli=False, stop=False,
                 exit_on_error=False, callback=None):
        self.location = location
        self.lgr = logging.getLogger('ioc_json')
        self.cli = cli
        self.stop = stop
        self.exit_on_error = exit_on_error
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

        key_and_value = {"host_domainname": "none"}

        for key, prop in props.items():

            if not key.startswith(prop_prefix):
                continue

            key = key.partition(":")[2]
            value = prop.value

            if key == "type":
                if value == "basejail":
                    # These were just clones on master.
                    value = "jail"
                    key_and_value["basejail"] = "yes"
            elif key == "hostname":
                hostname = props[f'{prop_prefix}:host_hostname']

                if value != hostname:
                    # This is safe to replace at this point.
                    # The user changed the wrong hostname key, we will move
                    # it to the right one now.
                    if hostname == uuid:
                        key_and_value["host_hostname"] = prop.value

                continue

            key_and_value[key] = value

        if not skip:
            # Set jailed=off and move the jailed dataset.
            try:
                self.zfs_set_property(f"{dataset}/root/data", "jailed", "off")
                self.zfs.get_dataset(f"{dataset}/root/data").rename(
                    f"{dataset}/data")
                self.zfs_set_property(f"{dataset}/data", jail_zfs_prop,
                                      f"iocage/jails/{uuid}/data")
                self.zfs_set_property(f"{dataset}/data", "jailed", "on")
            except libzfs.ZFSException as err:
                # The jailed dataset doesn't exist, which is OK.
                pass

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
            return "-"

    def zfs_set_property(self, identifier, key, value):
        ds = self._zfs_get_properties(identifier)

        if ":" in key:
            ds[key] = libzfs.ZFSUserProperty(value)
        else:
            ds[key].value = value

    def json_load(self):
        """Load the JSON at the location given. Returns a JSON object."""
        pool, iocroot = _get_pool_and_iocroot()
        version = self.json_get_version()
        jail_type, jail_uuid = self.location.rsplit("/", 2)[-2:]
        jail_dataset = self.zfs.get_dataset(
            f"{pool}/iocage/{jail_type}/{jail_uuid}")
        skip = False

        if jail_dataset.mountpoint is None:
            try:
                jail_dataset.mount_recursive()
            except libzfs.ZFSException as err:
                iocage.lib.ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": err
                }, exit_on_error=self.exit_on_error, _callback=self.callback,
                    silent=self.silent)

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
                            full_uuid = self.zfs_get_property(
                                self.location,
                                'org.freebsd.iocage:host_hostuuid')
                            jail_hostname = self.zfs_get_property(
                                self.location,
                                'org.freebsd.iocage:host_hostname')
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
                                exit_on_error=self.exit_on_error
                            ).list_get_jid(full_uuid)
                            if status:
                                iocage.lib.ioc_common.logit({
                                    "level"  : "INFO",
                                    "message":
                                        "Stopping jail to migrate UUIDs."
                                },
                                    _callback=self.callback,
                                    silent=self.silent)
                                iocage.lib.ioc_stop.IOCStop(
                                    full_uuid, self.location, conf,
                                    exit_on_error=self.exit_on_error,
                                    silent=True)

                            jail_zfs_prop = \
                                "org.freebsd.iocage:jail_zfs_dataset"
                            uuid_prop = "org.freebsd.iocage:host_hostuuid"
                            host_prop = "org.freebsd.iocage:host_hostname"

                            # Set jailed=off and move the jailed dataset.
                            self.zfs_set_property(f"{full_dataset}/data",
                                                  'jailed', 'off')

                            # We don't want to change a real hostname.
                            if jail_hostname == full_uuid:
                                self.zfs_set_property(full_dataset, host_prop,
                                                      short_uuid)

                            self.zfs_set_property(full_dataset, uuid_prop,
                                                  short_uuid)
                            self.zfs_set_property(f"{full_dataset}/data",
                                                  jail_zfs_prop,
                                                  f"iocage/jails/"
                                                  f"{short_uuid}/data")

                            self.zfs.get_dataset(full_dataset).rename(
                                short_dataset)
                            self.zfs_set_property(f"{short_dataset}/data",
                                                  "jailed", "on")

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
                conf = self.json_check_config(conf)
        except KeyError:
            conf = self.json_check_config(conf)

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

    def json_get_value(self, prop, default=False):
        """Returns a string with the specified prop's value."""
        old = False
        zpools = list(map(lambda x: x.name, list(self.zfs.pools)))

        if default:
            _, iocroot = _get_pool_and_iocroot()
            with open(f"{iocroot}/defaults.json", "r") as default_json:
                conf = json.load(default_json)

            if prop == "all":
                return conf

            return conf[prop]

        if prop == "pool":
            match = 0

            for pool in zpools:

                prop_ioc_active = self.zfs_get_property(
                    pool, "org.freebsd.ioc:active")
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
                    try:
                        zpool = zpools[0]
                    except IndexError:
                        iocage.lib.ioc_common.logit({
                            "level"  : "EXCEPTION",
                            "message": "No zpools found! Please create one "
                                       "before using iocage."
                        }, exit_on_error=self.exit_on_error,
                            _callback=self.callback,
                            silent=self.silent)

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

                    self.zfs_set_property(zpool, "org.freebsd.ioc:active",
                                          "yes")
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

    def json_set_value(self, prop, _import=False, default=False):
        """Set a property for the specified jail."""
        key, _, value = prop.partition("=")

        if not default:
            conf = self.json_load()
            uuid = conf["host_hostuuid"]
            status, jid = iocage.lib.ioc_list.IOCList().list_get_jid(uuid)
            conf[key] = value
            sysctls_cmd = ["sysctl", "-d", "security.jail.param"]
            jail_param_regex = re.compile("security.jail.param.")
            sysctls_list = su.Popen(sysctls_cmd, stdout=su.PIPE).communicate()[
                0].decode("utf-8").split()
            jail_params = [p.replace("security.jail.param.", "").replace(":",
                                                                         "")
                           for p in sysctls_list if re.match(jail_param_regex,
                                                             p)]
            single_period = ["allow_raw_sockets", "allow_socket_af",
                             "allow_set_hostname"]
            if key == "template":
                pool, iocroot = _get_pool_and_iocroot()
                old_location = f"{pool}/iocage/jails/{uuid}"
                new_location = f"{pool}/iocage/templates/{uuid}"

                if status:
                    iocage.lib.ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": f"{uuid} is running.\nPlease stop it first!"
                    }, exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)

                jails = iocage.lib.ioc_list.IOCList(
                    "uuid", exit_on_error=self.exit_on_error).list_datasets()
                for j in jails:
                    _uuid = jails[j]
                    _path = f"{jails[j]}/root"
                    t_old_path = f"{old_location}/root@{_uuid}"
                    t_path = f"{new_location}/root@{_uuid}"

                    if _uuid == uuid:
                        continue

                    origin = self.zfs_get_property(_path, 'origin')

                    if origin == t_old_path or origin == t_path:
                        _status, _ = iocage.lib.ioc_list.IOCList(
                        ).list_get_jid(_uuid)

                        if _status:
                            iocage.lib.ioc_common.logit({
                                "level"  : "EXCEPTION",
                                "message": f"{uuid} is running.\n"
                                           "Please stop it first!"
                            }, exit_on_error=self.exit_on_error,
                                _callback=self.callback,
                                silent=self.silent)

                if value == "yes":
                    try:
                        try:
                            jail_zfs_dataset = f"{pool}/" \
                                               f"{conf['jail_zfs_dataset']}"
                            self.zfs_set_property(jail_zfs_dataset,
                                                  "jailed", "off")
                        except libzfs.ZFSException as err:
                            # The dataset doesn't exist, that's OK
                            if err.code == libzfs.Error.NOENT:
                                pass
                            else:
                                # Danger, Will Robinson!
                                raise

                        self.zfs.get_dataset(old_location).rename(new_location)
                        conf["type"] = "template"

                        self.location = new_location.lstrip(pool).replace(
                            "/iocage", iocroot)

                        iocage.lib.ioc_common.logit({
                            "level"  : "INFO",
                            "message": f"{uuid} converted to a template."
                        },
                            _callback=self.callback,
                            silent=self.silent)

                        # Writing these now since the dataset will be readonly
                        self.json_check_prop(key, value, conf)
                        self.json_write(conf)

                        iocage.lib.ioc_common.logit({
                            "level"  : "INFO",
                            "message":
                                f"Property: {key} has been updated to {value}"
                        },
                            _callback=self.callback,
                            silent=self.silent)

                        self.zfs_set_property(new_location, "readonly", "on")
                        return
                    except libzfs.ZFSException:
                        iocage.lib.ioc_common.logit({
                            "level"  : "EXCEPTION",
                            "message": "A template by that name already"
                                       " exists!"
                        }, exit_on_error=self.exit_on_error,
                            _callback=self.callback,
                            silent=self.silent)

                elif value == "no":
                    if not _import:
                        self.zfs.get_dataset(new_location).rename(old_location)
                        conf["type"] = "jail"
                        self.location = old_location.lstrip(pool).replace(
                            "/iocage", iocroot)
                        self.zfs_set_property(old_location, "readonly", "off")

                        iocage.lib.ioc_common.logit({
                            "level"  : "INFO",
                            "message": f"{uuid} converted to a jail."
                        },
                            _callback=self.callback,
                            silent=self.silent)
                        self.lgr.disabled = True
        else:
            _, iocroot = _get_pool_and_iocroot()
            with open(f"{iocroot}/defaults.json", "r") as default_json:
                conf = json.load(default_json)

        if not default:
            self.json_check_prop(key, value, conf)
            self.json_write(conf)
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message":
                    f"Property: {key} has been updated to {value}"
            },
                _callback=self.callback,
                silent=self.silent)

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
                        ip = True if key == "ip4.addr" or key == "ip6.addr" \
                            else False
                        if ip and value == "none":
                            return

                        iocage.lib.ioc_common.checkoutput(
                            ["jail", "-m", f"jid={jid}",
                             f"{key}={value}"],
                            stderr=su.STDOUT)
                    except su.CalledProcessError as err:
                        raise RuntimeError(
                            f"{err.output.decode('utf-8').rstrip()}")
        else:
            if key in conf:
                conf[key] = value
                self.json_write(conf, "/defaults.json")

                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message":
                        f"Default Property: {key} has been updated to {value}"
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                iocage.lib.ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": f"{key} is not a valid property for default!"
                }, exit_on_error=self.exit_on_error, _callback=self.callback,
                    silent=self.silent)

    @staticmethod
    def json_get_version():
        """Sets the iocage configuration version."""
        version = "9"
        return version

    def json_check_config(self, conf, default=False):
        """
        Takes JSON as input and checks to see what is missing and adds the
        new keys with their default values if missing.
        """
        if os.geteuid() != 0:
            iocage.lib.ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": "You need to be root to convert the"
                           " configurations to the new format!"
            }, exit_on_error=self.exit_on_error, _callback=self.callback,
                silent=self.silent)

        pool, iocroot = _get_pool_and_iocroot()

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
        if not default:
            release = conf.get("release", None)

            if release is None:
                err_name = self.location.rsplit("/", 1)[-1]
                iocage.lib.ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": f"{err_name} has a corrupt configuration,"
                               " please destroy the jail."
                }, exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

            cloned_release = conf.get("cloned_release", "LEGACY_JAIL")

            try:
                freebsd_version = f"{iocroot}/releases/{conf['release']}" \
                                  "/root/bin/freebsd-version"
            except FileNotFoundError:
                freebsd_version = f"{iocroot}/templates/" \
                                  f"{conf['host_hostuuid']}" \
                                  "/root/bin/freebsd-version"
            except KeyError:
                # At this point it should be a real misconfigured jail
                uuid = self.location.rsplit("/", 1)[-1]
                raise RuntimeError("Configuration is missing!"
                                   f" Please destroy {uuid} and recreate"
                                   " it.")

            if conf["release"][:4].endswith("-"):
                # 9.3-RELEASE and under don't actually have this binary.
                release = conf["release"]
            else:
                with open(freebsd_version, "r") as r:
                    for line in r:
                        if line.startswith("USERLAND_VERSION"):
                            release = line.rstrip().partition("=")[2]
                            release = release.strip('"')

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

        # Version 6 keys
        conf["host_time"] = "yes"

        # Version 7 keys
        conf["depends"] = "none"

        # Version 8 migration from TAG to renaming dataset
        try:
            tag = conf["tag"]
            uuid = conf["host_hostuuid"]

            try:
                state = iocage.lib.ioc_common.checkoutput(
                    ["jls", "-j",
                     f"ioc-{uuid.replace('.', '_')}"], stderr=su.PIPE).split(
                )[5]
            except su.CalledProcessError:
                state = False

            # These are already good to go.
            if tag != uuid:
                date_fmt = "%Y-%m-%d@%H:%M:%S:%f"
                date_fmt_legacy = "%Y-%m-%d@%H:%M:%S"

                # We don't want to rename datasets to a bunch of dates.
                try:
                    datetime.datetime.strptime(tag, date_fmt)

                    # For writing later
                    tag = uuid
                except ValueError:
                    try:
                        # This will fail the first, making sure one more time
                        datetime.datetime.strptime(tag, date_fmt_legacy)

                        # For writing later
                        tag = uuid
                    except ValueError:
                        try:
                            if self.stop and state:
                                # This will allow the user to actually stop
                                # the running jails before migration.
                                return conf

                            if state:
                                iocage.lib.ioc_common.logit({
                                    "level"  : "EXCEPTION",
                                    "message": f"{uuid} ({tag}) is running,"
                                               " all jails must be stopped"
                                               " before iocage will"
                                               " continue migration"
                                }, exit_on_error=self.exit_on_error,
                                    _callback=self.callback,
                                    silent=self.silent)

                            try:
                                # Can't rename when the child is
                                # in a non-global zone
                                data_dataset = self.zfs.get_dataset(
                                    f"{pool}/iocage/jails/{uuid}/data"
                                )
                                dependents = data_dataset.dependents

                                self.zfs_set_property(
                                    f"{pool}/iocage/jails/{uuid}/data",
                                    "jailed", "off")
                                for dep in dependents:
                                    if dep.type != "FILESYSTEM":
                                        continue

                                    d = dep.name
                                    self.zfs_set_property(d, "jailed", "off")

                            except libzfs.ZFSException:
                                # No data dataset exists
                                pass

                            self.zfs.get_dataset(
                                f"{pool}/iocage/jails/{uuid}").rename(
                                f"{pool}/iocage/jails/{tag}")

                            # Easier.
                            su.check_call(["zfs", "rename", "-r",
                                           f"{pool}/iocage@{uuid}", f"@{tag}"])

                            try:
                                # The childern will also inherit this
                                self.zfs_set_property(
                                    f"{pool}/iocage/jails/{tag}/data",
                                    "jailed", "on")
                            except libzfs.ZFSException:
                                # No data dataset exists
                                pass

                            for line in fileinput.input(
                                    f"{iocroot}/jails/{tag}/root/etc/rc.conf",
                                    inplace=1):
                                print(line.replace(f'hostname="{uuid}"',
                                                   f'hostname="{tag}"').rstrip(
                                ))

                            if conf["basejail"] == "yes":
                                for line in fileinput.input(
                                        f"{iocroot}/jails/{tag}/fstab",
                                        inplace=1):
                                    print(line.replace(
                                        f'{uuid}', f'{tag}').rstrip())

                        except libzfs.ZFSException:
                            # A template, already renamed to a TAG
                            pass

                conf["host_hostuuid"] = tag

                if conf["host_hostname"] == uuid:
                    # They may have set their own, we don't want to trample it.
                    conf["host_hostname"] = tag
        except KeyError:
            # New jail creation
            pass

        # Version 9 keys
        try:
            dhcp = conf["dhcp"]
            bpf = conf["bpf"]
        except KeyError:
            dhcp = "off"
            bpf = "no"

        # Set all keys, even if it's the same value.
        conf["dhcp"] = dhcp
        conf["bpf"] = bpf

        # Set all keys, even if it's the same value.
        conf["CONFIG_VERSION"] = self.json_get_version()

        if not default:
            try:
                self.json_write(conf)
            except FileNotFoundError:
                # Dataset was renamed.
                self.location = f"{iocroot}/jails/{tag}"
                self.json_write(conf)
                messages = collections.OrderedDict([
                    ("1-NOTICE", "*" * 80),
                    ("2-WARNING", f"Jail: {uuid} was renamed to {tag}"),
                    ("3-NOTICE", f"{'*' * 80}\n"),
                    ("4-EXCEPTION", "Please issue your command again.")
                ])

                for level, msg in messages.items():
                    level = level.partition("-")[2]

                    iocage.lib.ioc_common.logit({
                        "level"  : level,
                        "message": msg
                    }, exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)

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
            "ip4_addr"             : ("string",),
            "ip4_saddrsel"         : ("0", "1",),
            "ip4"                  : ("new", "inherit", "none"),
            "ip6_addr"             : ("string",),
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
            "bpf"                  : ("no", "yes"),
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
            "comment"              : ("string",),
            "host_time"            : ("no", "yes"),
            "depends"              : ("string",)
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
            else:
                _type = "jails"

            uuid = conf["host_hostuuid"]

            if key == "quota":
                if value != "none" and not value.upper().endswith(("M", "G",
                                                                   "T")):
                    err = f"{value} should have a suffix ending in" \
                          " M, G, or T."
                    iocage.lib.ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": err
                    }, exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)

            self.zfs_set_property(f"{pool}/iocage/{_type}/{uuid}", key, value)

        elif key in props.keys():
            # Either it contains what we expect, or it's a string.
            for k in props[key]:
                if k in value:
                    return

            if props[key][0] == "string":
                return
            else:
                err = f"{value} is not a valid value for {key}.\n"

                if key not in ("interfaces", "memoryuse"):
                    msg = f"Value must be {' or '.join(props[key])}"

                elif key == "interfaces":
                    msg = "Interfaces must be specified as a pair.\n" \
                          "EXAMPLE: vnet0:bridge0, vnet1:bridge1"
                elif key == "memoryuse":
                    msg = "memoryuse requires at minimum a pair.\nEXAMPLE: " \
                          "8g:log"

                msg = err + msg
                iocage.lib.ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": msg
                }, exit_on_error=self.exit_on_error, _callback=self.callback,
                    silent=self.silent)
        else:
            if self.cli:
                msg = f"{key} cannot be changed by the user."
            else:
                if key not in conf.keys():
                    msg = f"{key} is not a valid property!"
                else:
                    return

            iocage.lib.ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": msg
            }, exit_on_error=self.exit_on_error, _callback=self.callback,
                silent=self.silent)

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
        _path = self.zfs_get_property(f"{pool}/iocage/jails/{uuid}",
                                      "mountpoint")

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
                    return iocage.lib.ioc_exec.IOCExec(
                        prop_cmd, uuid, _path, plugin=True,
                        exit_on_error=self.exit_on_error,
                        silent=True).exec_jail()
            else:
                return settings
        except KeyError:
            raise RuntimeError(
                f"Key: \"{prop_error}\" does not exist!")

    def json_plugin_set_value(self, prop):
        pool, iocroot = _get_pool_and_iocroot()
        conf = self.json_load()
        uuid = conf["host_hostuuid"]
        _path = self.zfs_get_property(f"{pool}/iocage/jails/{uuid}",
                                      "mountpoint")
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
            iocage.lib.ioc_exec.IOCExec(
                prop_cmd, uuid, _path,
                exit_on_error=self.exit_on_error).exec_jail()

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
                iocage.lib.ioc_exec.IOCExec(
                    servicerestart, uuid, _path,
                    exit_on_error=self.exit_on_error).exec_jail()

            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": f"\nKey: {keys} has been updated to {value}"
            },
                _callback=self.callback,
                silent=self.silent)
        except KeyError:
            iocage.lib.ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": f"Key: \"{key}\" does not exist!"
            }, exit_on_error=self.exit_on_error, _callback=self.callback,
                silent=self.silent)

    def json_check_default_config(self):
        """This sets up the default configuration for jails."""
        _, iocroot = _get_pool_and_iocroot()
        default_json_location = f"{iocroot}/defaults.json"
        with open("/etc/hostid", "r") as _file:
            hostid = _file.read().strip()

        try:
            with open(default_json_location, "r") as default_json:
                default_props = json.load(default_json)
                default_props = self.json_check_config(default_props,
                                                       default=True)
        except FileNotFoundError:
            default_props = {
                "CONFIG_VERSION"       : self.json_get_version(),
                "interfaces"           : "vnet0:bridge0",
                "host_domainname"      : "none",
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
                "type"                 : "jail",
                "bpf"                  : "no",
                "dhcp"                 : "off",
                "boot"                 : "off",
                "notes"                : "none",
                "owner"                : "root",
                "priority"             : "99",
                "last_started"         : "none",
                "template"             : "no",
                "hostid"               : hostid,
                "jail_zfs"             : "off",
                "jail_zfs_mountpoint"  : "none",
                "mount_procfs"         : "0",
                "mount_linprocfs"      : "0",
                "count"                : "1",
                "vnet"                 : "off",
                "basejail"             : "no",
                "comment"              : "none",
                "host_time"            : "yes",
                "sync_state"           : "none",
                "sync_target"          : "none",
                "sync_tgt_zpool"       : "none",
                "compression"          : "lz4",
                "origin"               : "readonly",
                "quota"                : "none",
                "mountpoint"           : "readonly",
                "compressratio"        : "readonly",
                "available"            : "readonly",
                "used"                 : "readonly",
                "dedup"                : "off",
                "reservation"          : "none"
            }
        finally:
            # They may have had new keys added to their default
            # configuration, or it never existed.
            self.json_write(default_props, default_json_location)

        return default_props
