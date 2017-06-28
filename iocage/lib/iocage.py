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
import collections
import datetime
import json
import operator
import os
import subprocess as su

import libzfs

import iocage.lib.ioc_clean as ioc_clean
import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_create as ioc_create
import iocage.lib.ioc_destroy as ioc_destroy
import iocage.lib.ioc_exec as ioc_exec
import iocage.lib.ioc_fetch as ioc_fetch
import iocage.lib.ioc_fstab as ioc_fstab
import iocage.lib.ioc_image as ioc_image
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list
import iocage.lib.ioc_start as ioc_start
import iocage.lib.ioc_stop as ioc_stop


class PoolAndDataset(object):
    def __init__(self):
        self.pool = ioc_json.IOCJson().json_get_value("pool")
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

    def get_pool(self):
        """
        Helper to get the current pool.

        Return:
                string: with the pool name.
        """
        return self.pool

    def get_datasets(self, option_type):
        """
        Helper to get datasets.

        Return:
                generator: from libzfs.ZFSDataset.
        """
        __types = {
            'all'     : '/iocage/jails', 'base': '/iocage/releases',
            'template': '/iocage/templates', 'uuid': '/iocage/jails',
            'root'    : '/iocage',
        }

        if option_type in __types.keys():
            return self.zfs.get_dataset(
                f"{self.pool}{__types[option_type]}").children

    def get_iocroot(self):
        """
        Helper to get the iocroot.

        Return:
                string: with the iocroot name.
        """
        return ioc_json.IOCJson(self.pool).json_get_value("iocroot")


class IOCage(object):
    def __init__(self, jail=None, rc=False, callback=None, silent=False,
                 activate=False, skip_jails=False):
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

        if not activate:
            self.pool = PoolAndDataset().get_pool()
            self.iocroot = PoolAndDataset().get_iocroot()

            if not skip_jails:
                # When they need to destroy a jail with a missing or bad
                # configuration, this gets in our way otherwise.
                self.jails, self._paths = self.list("uuid")

        self.jail = jail
        self.rc = rc
        self._all = True if self.jail and 'ALL' in self.jail else False
        self.callback = ioc_common.callback if not callback else callback
        self.silent = silent

    def __all__(self, jail_order, action):
        # So we can properly start these.
        self._all = False

        for j in jail_order:
            # We want this to be the real jail now.
            self.jail = j
            tag, uuid, path = self.__check_jail_existence__()
            status, jid = self.list("jid", uuid=uuid)

            if action == 'stop':
                self.stop(j)
            elif action == 'start':
                if not status:
                    err, msg = self.start(j)

                    if err:
                        self.callback({'level': 'ERROR', 'message': msg})
                else:
                    message = f"{uuid} ({j}) is already running!"
                    self.callback({'level': 'WARNING', 'message': message})

    def __jail_order__(self, action):
        """Helper to gather lists of all the jails by order and boot order."""
        jail_order = {}
        boot_order = {}

        _reverse = True if action == 'stop' else False

        for jail in self.jails:
            self.jail = jail
            tag, uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(path).json_load()
            boot = conf['boot']
            priority = conf['priority']
            jail_order[jail] = int(priority)

            # This removes having to grab all the JSON again later.
            if boot == 'on':
                boot_order[jail] = int(priority)

            jail_order = collections.OrderedDict(
                sorted(jail_order.items(), key=operator.itemgetter(1),
                       reverse=_reverse))
            boot_order = collections.OrderedDict(
                sorted(boot_order.items(), key=operator.itemgetter(1),
                       reverse=_reverse))

        if self.rc:
            self.__rc__(boot_order, action)
        elif self._all:
            self.__all__(jail_order, action)

    def __rc__(self, boot_order, action):
        """Helper to start all jails with boot=on"""
        # So we can properly start these.
        self.rc = False

        for j in boot_order.keys():
            # We want this to be the real jail now.
            self.jail = j

            tag, uuid, path = self.__check_jail_existence__()
            status, _ = self.list("jid", uuid=uuid)

            if action == 'stop':
                if status:
                    message = f"  Stopping {uuid} ({j})"
                    self.callback({'level': 'INFO', 'message': message})

                    self.stop(j)
                else:
                    message = f"{uuid} ({j}) is not running!"
                    self.callback({'level': 'INFO', 'message': message})
            elif action == 'start':
                if not status:
                    err, msg = self.start(j)

                    if err:
                        self.callback({'level': 'ERROR', 'message': msg})
                else:
                    message = f"{uuid} ({j}) is already running!"
                    self.callback({'level': 'WARNING', 'message': message})

    def __check_jail_existence__(self):
        """
        Helper to check if jail dataset exists
        Return:
                tuple: The jails tag, uuid, path
        """
        _jail = {tag: uuid for (tag, uuid) in self.jails.items() if
                 uuid.startswith(self.jail) or tag == self.jail}

        if len(_jail) == 1:
            tag, uuid = next(iter(_jail.items()))
            path = self._paths[tag]

            return tag, uuid, path
        elif len(_jail) > 1:
            # Do another search, this time more exact.
            _jail = {tag: uuid for (tag, uuid) in _jail.items() if
                     uuid == self.jail or tag == self.jail}

            if len(_jail) == 1:
                tag, uuid = next(iter(_jail.items()))
                path = self._paths[tag]

                return tag, uuid, path
            elif len(_jail) > 1:
                msg = f"Multiple jails found for {self.jail}:"

                for j, u in sorted(_jail.items()):
                    msg += f"\n  {j} ({u})"

                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": f"{self.jail} not found!"
                },
                    _callback=self.callback,
                    silent=self.silent)
        else:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": f"{self.jail} not found!"
            },
                _callback=self.callback,
                silent=self.silent)

    @staticmethod
    def __check_jail_type__(_type, uuid, tag):
        """
        Return:
            tuple: True if error with a message, or False/None
        """
        if _type in ('jail', 'plugin'):
            return False, None
        elif _type == 'basejail':
            return (True, "Please run \"iocage migrate\" before trying to"
                          f" start {uuid} ({tag})")
        elif _type == 'template':
            return (True, "Please convert back to a jail before trying to"
                          f" start {uuid} ({tag})")
        else:
            return True, f"{_type} is not a supported jail type."

    @staticmethod
    def __mount__(path, _type):
        if _type == "devfs":
            cmd = ["mount", "-t", "devfs", "devfs", path]
        else:
            cmd = ["mount", "-a", "-F", path]

        _, stderr = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

        return stderr

    @staticmethod
    def __umount__(path, _type):
        if _type == "devfs":
            cmd = ["umount", path]
        else:
            cmd = ["umount", "-a", "-F", path]

        _, stderr = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

        return stderr

    def __remove_activate_comment(self, pool):
        """Removes old legacy comment for zpool activation"""
        # Check and clean if necessary iocage_legacy way
        # to mark a ZFS pool as usable (now replaced by ZFS property)
        comment = self.zfs.get(pool.name).properties["comment"]

        if comment.value == "iocage":
            comment.value = "-"

    def activate(self, zpool):
        """Activates the zpool for iocage usage"""
        pools = list(self.zfs.pools)
        prop = "org.freebsd.ioc:active"
        match = False

        for pool in pools:
            if pool.name == zpool:
                match = True

        if not match:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": f"ZFS pool '{zpool}' not found!"
            },
                _callback=self.callback,
                silent=self.silent)

        for pool in pools:
            ds = self.zfs.get_dataset(pool.name)
            if pool.name == zpool:
                ds.properties[prop] = libzfs.ZFSUserProperty("yes")
            else:
                ds.properties[prop] = libzfs.ZFSUserProperty("no")

            self.__remove_activate_comment(pool)

    def chroot(self, command):
        """Chroots into a jail and runs a command, or the shell."""
        # We may be getting ';', '&&' and so forth. Adding the shell for
        # safety.
        command = list(command)

        # We may be getting ';', '&&' and so forth. Adding the shell for
        # safety.
        if len(command) == 1:
            command = ["/bin/sh", "-c"] + command

        tag, uuid, path = self.__check_jail_existence__()
        devfs_stderr = self.__mount__(f"{path}/root/dev", "devfs")

        if devfs_stderr:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": "Mounting devfs failed!"
            },
                _callback=self.callback,
                silent=self.silent)

        fstab_stderr = self.__mount__(f"{path}/fstab", "fstab")

        if fstab_stderr:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": "Mounting fstab failed!"
            },
                _callback=self.callback,
                silent=self.silent)

        chroot = su.Popen(["chroot", f"{path}/root"] + command)
        chroot.communicate()

        udevfs_stderr = self.__umount__(f"{path}/root/dev", "devfs")
        if udevfs_stderr:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": "Unmounting devfs failed!"
            },
                _callback=self.callback,
                silent=self.silent)

        ufstab_stderr = self.__umount__(f"{path}/fstab", "fstab")
        if ufstab_stderr:
            if b"fstab reading failure\n" in ufstab_stderr:
                # By default our fstab is empty and will throw this error.
                pass
            else:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": "Unmounting fstab failed!"
                },
                    _callback=self.callback,
                    silent=self.silent)

        if chroot.returncode:
            ioc_common.logit({
                "level"  : "WARNING",
                "message": "Chroot had a non-zero exit code!"
            },
                _callback=self.callback,
                silent=self.silent)

    def clean(self, d_type):
        """Destroys all of a specified dataset types."""
        if d_type == "jails":
            ioc_clean.IOCClean(silent=self.silent).clean_jails()
            ioc_common.logit({
                "level"  : "INFO",
                "message": "All iocage jail datasets have been destroyed."
            },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "all":
            ioc_clean.IOCClean(silent=self.silent).clean_all()
            ioc_common.logit({
                "level"  : "INFO",
                "message": "All iocage datasets have been destroyed."
            },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "release":
            ioc_clean.IOCClean(silent=self.silent).clean_releases()
            ioc_common.logit({
                "level"  : "INFO",
                "message": "All iocage RELEASE and jail datasets have been"
                           " destroyed."
            },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "template":
            ioc_clean.IOCClean(silent=self.silent).clean_templates()
            ioc_common.logit({
                "level"  : "INFO",
                "message": "All iocage template datasets have been destroyed."
            },
                _callback=self.callback,
                silent=self.silent)
        else:
            ioc_common.logit({
                "level"  : "EXCEPTIONG",
                "message": "Please specify a dataset type to clean!"
            },
                _callback=self.callback,
                silent=self.silent)

    def create(self, release, props, count=0, pkglist=None, template=False,
               short=False, uuid=None, basejail=False, empty=False,
               clone=None, skip_batch=False):
        """Creates the jail dataset"""
        count = 0 if count == 1 and not skip_batch else count

        if short and uuid:
            uuid = uuid[:8]

            if len(uuid) != 8:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": "Need a minimum of 8 characters to use --short"
                               " (-s) and --uuid (-u) together!"
                },
                    _callback=self.callback,
                    silent=self.silent)

        if not template and not release and not empty and not clone:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": "Must supply either --template (-t) or"
                           " --release (-r)!"
            },
                _callback=self.callback,
                silent=self.silent)

        if not os.path.isdir(
                f"{self.iocroot}/releases/{release}") and not template and \
                not empty and not clone:
            freebsd_version = ioc_common.checkoutput(["freebsd-version"])

            if "HBSD" in freebsd_version:
                hardened = True
            else:
                hardened = False

            ioc_fetch.IOCFetch(release, hardened=hardened,
                               silent=self.silent).fetch_release()

        if clone:
            _, clone_uuid, _ = self.__check_jail_existence__()
            status, _ = self.list("jid", uuid=clone_uuid)
            if status:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": f"Jail: {self.jail} must not be running to be"
                               " cloned!"
                },
                    _callback=self.callback,
                    silent=self.silent)

            release = clone_uuid
            clone = self.jail

        try:
            if count > 1 and not skip_batch:
                for j in range(1, count + 1):
                    self.create(release, props, j, pkglist=pkglist,
                                template=template, short=short, uuid=uuid,
                                basejail=basejail, empty=empty, clone=clone,
                                skip_batch=True)
            else:
                ioc_create.IOCCreate(release, props, count, pkglist,
                                     template=template, short=short, uuid=uuid,
                                     basejail=basejail, empty=empty,
                                     clone=clone,
                                     silent=self.silent).create_jail()
        except RuntimeError as err:
            return True, err

        return False, None

    @staticmethod
    def destroy(path, parse=False):
        """Destroys the supplied path"""
        if parse:
            # This skips some of the nice things destroy_jail does. Namely
            # loading a configuration, as these aren't jails being destroyed.
            ioc_destroy.IOCDestroy().__destroy_parse_datasets__(path)
        else:
            ioc_destroy.IOCDestroy().destroy_jail(path)

    def df(self, long=False):
        """Returns a list containing the resource usage of all jails"""
        jails, paths = self.list("uuid")
        jail_list = []

        for jail in jails:
            full_uuid = jails[jail]

            if not long:
                uuid = full_uuid[:8]
            else:
                uuid = full_uuid

            path = paths[jail]
            conf = ioc_json.IOCJson(path).json_load()
            mountpoint = f"{self.pool}/iocage/jails/{full_uuid}"

            tag = conf["tag"]
            template = conf["type"]

            if template == "template":
                mountpoint = f"{self.pool}/iocage/templates/{tag}"

            ds = self.zfs.get_dataset(mountpoint)
            zconf = ds.properties

            compressratio = zconf["compressratio"].value
            reservation = zconf["reservation"].value
            quota = zconf["quota"].value
            used = zconf["used"].value
            available = zconf["available"].value

            jail_list.append([uuid, compressratio, reservation, quota, used,
                              available, tag])

        return jail_list

    def exec(self, command, host_user="root", jail_user=None, console=False):
        """Executes a command in the jail as the supplied users."""
        if host_user and jail_user:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": "Please only specify either host_user or"
                           " jail_user, not both!"
            },
                _callback=self.callback,
                silent=self.silent)

        tag, uuid, path = self.__check_jail_existence__()
        msg, err = ioc_exec.IOCExec(command, uuid, tag, path, host_user,
                                    jail_user, console=console,
                                    silent=self.silent).exec_jail()

        if not console:
            if err:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": err
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

    def export(self):
        """Will export a jail"""
        tag, uuid, path = self.__check_jail_existence__()
        status, _ = self.list("jid", uuid=uuid)

        if status:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": f"{uuid} ({tag}) is runnning, stop the jail before"
                           " exporting!"
            },
                _callback=self.callback,
                silent=self.silent)

        ioc_image.IOCImage().export_jail(uuid, tag, path)

    def fetch(self, **kwargs):
        """Fetches a release or plugin."""
        release = kwargs.pop("release", None)
        name = kwargs.pop("name", None)
        props = kwargs.pop("props", ())
        plugins = kwargs.pop("plugins", False)
        plugin_file = kwargs.pop("plugin_file", False)
        count = kwargs.pop("count", 1)
        accept = kwargs.pop("accept", False)

        freebsd_version = ioc_common.checkoutput(["freebsd-version"])
        arch = os.uname()[4]

        if not kwargs["files"]:
            if arch == "arm64":
                kwargs["files"] = ("MANIFEST", "base.txz", "doc.txz")
            else:
                kwargs["files"] = ("MANIFEST", "base.txz", "lib32.txz",
                                   "doc.txz")

        if "HBSD" in freebsd_version:
            if kwargs["server"] == "ftp.freebsd.org":
                kwargs["hardened"] = True
            else:
                kwargs["hardened"] = False
        else:
            kwargs["hardened"] = False

        if plugins or plugin_file:
            ip = [x for x in props if x.startswith("ip4_addr") or
                  x.startswith("ip6_addr")]
            if not ip:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": "An IP address is needed to fetch a plugin!\n"
                               "Please specify ip(4|6)"
                               "_addr=\"INTERFACE|IPADDRESS\"!"
                },
                    _callback=self.callback,
                    silent=self.silent)

            if plugins:
                ioc_fetch.IOCFetch(
                    release, plugin=name, **kwargs).fetch_plugin_index(
                    props, accept_license=accept)
                return

            if count == 1:
                ioc_fetch.IOCFetch(release, **kwargs).fetch_plugin(name,
                                                                   props, 0,
                                                                   accept)
            else:
                for j in range(1, count + 1):
                    ioc_fetch.IOCFetch(release, **kwargs).fetch_plugin(name,
                                                                       props,
                                                                       j,
                                                                       accept)
        else:
            ioc_fetch.IOCFetch(release, **kwargs).fetch_release()

    def fstab(self, action, source, destination, fstype, options, dump, _pass,
              index=None, add_path=False):
        """Adds an fstab entry for a jail"""
        tag, uuid, path = self.__check_jail_existence__()

        if add_path:
            destination = f"{self.iocroot}/jails/{uuid}/root{destination}"

        if len(destination) > 88:
            ioc_common.logit({
                "level"  : "WARNING",
                "message": "The destination's mountpoint exceeds 88 "
                           "characters, this may cause failure!"
            },
                _callback=self.callback,
                silent=self.silent)

        ioc_fstab.IOCFstab(uuid, tag, action, source, destination, fstype,
                           options, dump, _pass, index=index)

    def get(self, prop, recursive=False, plugin=False, pool=False):
        """Get a jail property"""
        if not recursive:
            tag, uuid, path = self.__check_jail_existence__()
            status, jid = self.list("jid", uuid=uuid)

            if pool:
                return self.pool

            if prop == "state":
                if status:
                    state = "up"
                else:
                    state = "down"

                return state
            elif plugin:
                _prop = prop.split(".")
                props = ioc_json.IOCJson(path).json_plugin_get_value(_prop)

                if isinstance(props, dict):
                    return json.dumps(props, indent=4)
                else:
                    return props[0].decode("utf-8")
            elif prop == "all":
                props = ioc_json.IOCJson(path).json_get_value(prop)

                return props
            elif prop == "fstab":
                fstab_list = []
                index = 0

                with open(f"{self.iocroot}/jails/{uuid}/fstab", "r") as fstab:
                    for line in fstab.readlines():
                        line = line.rsplit("#")[0].rstrip()
                        fstab_list.append([index, line.replace("\t", " ")])
                        index += 1

                    return fstab_list
            else:
                try:
                    return ioc_json.IOCJson(path).json_get_value(prop)
                except KeyError:
                    ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": f"{prop} is not a valid property!"
                    },
                        _callback=self.callback,
                        silent=self.silent)
        else:
            jail_list = []

            for j in self.jails:
                uuid = self.jails[j]
                path = self._paths[j]
                try:
                    if prop == "state":
                        status, _ = self.list("jid", uuid=uuid)

                        if status:
                            state = "up"
                        else:
                            state = "down"

                        jail_list.append([uuid, j, state])
                    elif prop == "all":
                        props = ioc_json.IOCJson(path).json_get_value(prop)

                        for p, v in props.items():
                            jail_list.append([uuid, j, f"{p}:{v}"])
                    else:
                        jail_list.append(
                            [uuid, j, ioc_json.IOCJson(path).json_get_value(
                                prop)])
                except KeyError:
                    ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": f"{prop} is not a valid property!"
                    },
                        _callback=self.callback,
                        silent=self.silent)

            return jail_list

    def import_(self):
        """Imports a jail"""
        ioc_image.IOCImage().import_jail(self.jail)

    @staticmethod
    def list(lst_type, header=False, long=False, sort="tag", uuid=None,
             plugin=False):
        """Returns a list of lst_type"""
        if lst_type == "jid":
            return ioc_list.IOCList().list_get_jid(uuid)

        return ioc_list.IOCList(lst_type, header, long, sort,
                                plugin=plugin).list_datasets()

    def restart(self, soft=False):
        if self._all:
            if not soft:
                self.__jail_order__("stop")
                # This gets unset each time.
                self._all = True

                self.__jail_order__("start")
            else:
                for j in self.jails:
                    self.jail = j
                    self.__soft_restart__()
        else:
            if not soft:
                self.stop()
                self.start()
            else:
                self.__soft_restart__()

    def rollback(self, name):
        """Rolls back a jail and all datasets to the supplied snapshot"""
        tag, uuid, path = self.__check_jail_existence__()
        conf = ioc_json.IOCJson(path, silent=self.silent).json_load()

        if conf["template"] == "yes":
            target = f"{self.pool}/iocage/templates/{tag}"
        else:
            target = f"{self.pool}/iocage/jails/{uuid}"

        try:
            datasets = self.zfs.get_dataset(target)
            self.zfs.get_snapshot(f"{datasets.name}@{name}")
        except libzfs.ZFSException as err:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": err
            },
                _callback=self.callback,
                silent=self.silent)

        for dataset in datasets.dependents:
            if dataset.type == libzfs.DatasetType.FILESYSTEM:
                self.zfs.get_snapshot(f"{dataset.name}@{name}").rollback()

        # datasets is actually the parent.
        self.zfs.get_snapshot(f"{datasets.name}@{name}").rollback()

        ioc_common.logit({
            "level"  : "INFO",
            "message": f"Rolled back to: {target}"
        },
            _callback=self.callback,
            silent=self.silent)

    def set(self, prop, plugin=False):
        """Sets a property for a jail or plugin"""
        prop = " ".join(prop)  # We don't want a tuple.

        if self.jail == "default":
            ioc_json.IOCJson().json_check_default_config()
            default = True
        else:
            default = False

        if "template=no" in prop:
            self.jail = f"{self.jail} (template)"

        if not default:
            tag, uuid, path = self.__check_jail_existence__()
            iocjson = ioc_json.IOCJson(path, cli=True)

            if "template" in prop.split("=")[0]:
                if "template" in path and prop != "template=no":
                    ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": f"{uuid} ({tag}) is already a template!"
                    },
                        _callback=self.callback,
                        silent=self.silent)
                elif "template" not in path and prop != "template=yes":
                    ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": f"{uuid} ({tag}) is already a jail!"
                    },
                        _callback=self.callback,
                        silent=self.silent)

            if plugin:
                _prop = prop.split(".")
                ioc_json.IOCJson(path, cli=True).json_plugin_set_value(_prop)
            else:
                try:
                    # We use this to test if it's a valid property at all.
                    _prop = prop.partition("=")[0]
                    self.get(_prop)

                    # The actual setting of the property.
                    iocjson.json_set_value(prop)
                except KeyError:
                    _prop = prop.partition("=")[0]
                    ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": f"{_prop} is not a valid property!"
                    },
                        _callback=self.callback,
                        silent=self.silent)
        else:
            ioc_json.IOCJson(self.iocroot).json_set_value(prop, default=True)

    def snap_list(self, long=True):
        """Gathers a list of snapshots and returns it"""
        tag, uuid, path = self.__check_jail_existence__()
        conf = ioc_json.IOCJson(path, silent=self.silent).json_load()
        snap_list = []

        if conf["template"] == "yes":
            full_path = f"{self.pool}/iocage/templates/{tag}"
        else:
            full_path = f"{self.pool}/iocage/jails/{uuid}"

        snapshots = self.zfs.get_dataset(full_path)

        for snap in snapshots.snapshots_recursive:
            snap_name = snap.name.rsplit("@")[1] if not long else snap.name
            root_snap_name = snap.name.rsplit("@")[0].split("/")[-1]

            if root_snap_name == "root":
                snap_name += "/root"
            elif root_snap_name != uuid and root_snap_name != tag:
                # basejail datasets.
                continue

            creation = snap.properties["creation"].value
            used = snap.properties["used"].value
            referenced = snap.properties["referenced"].value

            snap_list.append([snap_name, creation, referenced, used])

        return snap_list

    def __soft_restart__(self):
        """
        Executes a soft reboot by keeping the jail network stack intact,
        but executing the rc scripts.
        """
        tag, uuid, path = self.__check_jail_existence__()
        status, jid = self.list("jid", uuid=uuid)
        conf = ioc_json.IOCJson(path, silent=self.silent).json_load()

        # These need to be a list.
        exec_start = conf["exec_start"].split()
        exec_stop = conf["exec_stop"].split()
        exec_fib = conf["exec_fib"]

        if status:
            ioc_common.logit({
                "level"  : "INFO",
                "message": f"Soft restarting {uuid} ({self.jail})"
            },
                _callback=self.callback,
                silent=self.silent)

            stop_cmd = ["setfib", exec_fib, "jexec", f"ioc-{uuid}"] + \
                       exec_stop
            su.Popen(stop_cmd, stdout=su.PIPE,
                     stderr=su.PIPE).communicate()

            su.Popen(["pkill", "-j", jid]).communicate()
            start_cmd = ["setfib", exec_fib, "jexec", f"ioc-{uuid}"] + \
                        exec_start
            su.Popen(start_cmd, stdout=su.PIPE,
                     stderr=su.PIPE).communicate()
            ioc_json.IOCJson(path, silent=True).json_set_value(
                "last_started="
                f"{datetime.datetime.utcnow().strftime('%F %T')}")
        else:
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"{self.jail} is not running!"
            },
                _callback=self.callback,
                silent=self.silent)

    def start(self, jail=None):
        """Checks jails type and existence, then starts the jail"""
        if self.rc or self._all:
            if not jail:
                self.__jail_order__("start")
        else:
            tag, uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(path, silent=self.silent).json_load()
            err, msg = self.__check_jail_type__(conf["type"], uuid, tag)
            depends = conf["depends"].split()

            if not err:
                for depend in depends:
                    if depend != "none":
                        self.jail = depend
                        self.start()

                ioc_start.IOCStart(uuid, tag, path, conf,
                                   callback=self.callback, silent=self.silent)

                return False, None
            else:
                if jail:
                    return err, msg
                else:
                    self.callback({"level": "ERROR", "message": msg})
                    exit(1)

    def stop(self, jail=None):
        """Stops the jail."""
        if self.rc or self._all:
            if not jail:
                self.__jail_order__("stop")
        else:
            tag, uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(path, silent=self.silent).json_load()
            ioc_stop.IOCStop(uuid, tag, path, conf, silent=self.silent)
