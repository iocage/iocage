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
import uuid

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
import libzfs


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
            'all': '/iocage/jails',
            'base': '/iocage/releases',
            'template': '/iocage/templates',
            'uuid': '/iocage/jails',
            'root': '/iocage',
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
    def __init__(self,
                 jail=None,
                 rc=False,
                 callback=None,
                 silent=False,
                 activate=False,
                 skip_jails=False,
                 exit_on_error=False):
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.exit_on_error = exit_on_error

        if not activate:
            self.pool = PoolAndDataset().get_pool()
            self.iocroot = PoolAndDataset().get_iocroot()

            if not skip_jails:
                # When they need to destroy a jail with a missing or bad
                # configuration, this gets in our way otherwise.
                self.jails = self.list("uuid")

        self.skip_jails = skip_jails
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
            uuid, path = self.__check_jail_existence__()
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
            uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(
                path, exit_on_error=self.exit_on_error).json_load()
            boot = conf['boot']
            priority = conf['priority']
            jail_order[jail] = int(priority)

            # This removes having to grab all the JSON again later.

            if boot == 'on':
                boot_order[jail] = int(priority)

            jail_order = collections.OrderedDict(
                sorted(
                    jail_order.items(),
                    key=operator.itemgetter(1),
                    reverse=_reverse))
            boot_order = collections.OrderedDict(
                sorted(
                    boot_order.items(),
                    key=operator.itemgetter(1),
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

            uuid, path = self.__check_jail_existence__()
            status, _ = self.list("jid", uuid=uuid)

            if action == 'stop':
                if status:
                    message = f"  Stopping {uuid}"
                    self.callback({'level': 'INFO', 'message': message})

                    self.stop(j)
                else:
                    message = f"{uuid} is not running!"
                    self.callback({'level': 'INFO', 'message': message})
            elif action == 'start':
                if not status:
                    message = f"  Starting {uuid}"
                    self.callback({'level': 'INFO', 'message': message})

                    err, msg = self.start(j)

                    if err:
                        self.callback({'level': 'ERROR', 'message': msg})
                else:
                    message = f"{uuid} is already running!"
                    self.callback({'level': 'WARNING', 'message': message})

    def __check_jail_existence__(self):
        """
        Helper to check if jail dataset exists
        Return:
                tuple: The jails uuid, path
        """

        if os.path.isdir(f"{self.iocroot}/jails/{self.jail}"):
            path = f"{self.iocroot}/jails/{self.jail}"

            return self.jail, path
        elif os.path.isdir(f"{self.iocroot}/templates/{self.jail}"):
            path = f"{self.iocroot}/templates/{self.jail}"

            return self.jail, path
        else:
            if self.skip_jails:
                # We skip jails for performance, but if they didn't match be
                #  now need to gather the list and iterate.
                self.jails = self.list("uuid")

            # We got a partial, time to search.
            _jail = {
                uuid: path
                for (uuid, path) in self.jails.items()
                if uuid.startswith(self.jail)
            }

            if len(_jail) == 1:
                uuid, path = next(iter(_jail.items()))

                return uuid, path
            elif len(_jail) > 1:
                msg = f"Multiple jails found for {self.jail}:"

                for u, p in sorted(_jail.items()):
                    msg += f"\n  {u} ({p})"

                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": msg
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)
            else:
                msg = f"{self.jail} not found!"

                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": msg
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

    @staticmethod
    def __check_jail_type__(_type, uuid):
        """
        Return:
            tuple: True if error with a message, or False/None
        """

        if _type in ('jail', 'plugin'):
            return False, None
        elif _type == 'basejail':
            return (True, "Please run \"iocage migrate\" before trying to"
                    f" start {uuid}")
        elif _type == 'template':
            return (True, "Please convert back to a jail before trying to"
                    f" start {uuid}")
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
                if pool.status != "UNAVAIL":
                    match = True
                else:
                    ioc_common.logit(
                        {
                            "level":
                            "EXCEPTION",
                            "message":
                            f"ZFS pool '{zpool}' is UNAVAIL!\nPlease"
                            f" check zpool status {zpool} for more"
                            " information."
                        },
                        exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)

        if not match:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"ZFS pool '{zpool}' not found!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        for pool in pools:
            if pool.status != "UNAVAIL":
                ds = self.zfs.get_dataset(pool.name)
            else:
                continue

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

        uuid, path = self.__check_jail_existence__()
        devfs_stderr = self.__mount__(f"{path}/root/dev", "devfs")

        if devfs_stderr:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Mounting devfs failed!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        fstab_stderr = self.__mount__(f"{path}/fstab", "fstab")

        if fstab_stderr:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Mounting fstab failed!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        chroot = su.Popen(["chroot", f"{path}/root"] + command)
        chroot.communicate()

        udevfs_stderr = self.__umount__(f"{path}/root/dev", "devfs")

        if udevfs_stderr:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Unmounting devfs failed!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        ufstab_stderr = self.__umount__(f"{path}/fstab", "fstab")

        if ufstab_stderr:
            if b"fstab reading failure\n" in ufstab_stderr:
                # By default our fstab is empty and will throw this error.
                pass
            else:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": "Unmounting fstab failed!"
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

        if chroot.returncode:
            ioc_common.logit(
                {
                    "level": "WARNING",
                    "message": "Chroot had a non-zero exit code!"
                },
                _callback=self.callback,
                silent=self.silent)

    def clean(self, d_type):
        """Destroys all of a specified dataset types."""

        if d_type == "jails":
            ioc_clean.IOCClean(
                silent=self.silent,
                exit_on_error=self.exit_on_error).clean_jails()
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "All iocage jail datasets have been destroyed."
                },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "all":
            ioc_clean.IOCClean(
                silent=self.silent,
                exit_on_error=self.exit_on_error).clean_all()
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "All iocage datasets have been destroyed."
                },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "release":
            ioc_clean.IOCClean(
                silent=self.silent,
                exit_on_error=self.exit_on_error).clean_releases()
            ioc_common.logit(
                {
                    "level":
                    "INFO",
                    "message":
                    "All iocage RELEASE and jail datasets have been"
                    " destroyed."
                },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "template":
            ioc_clean.IOCClean(
                silent=self.silent,
                exit_on_error=self.exit_on_error).clean_templates()
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message":
                    "All iocage template datasets have been destroyed."
                },
                _callback=self.callback,
                silent=self.silent)
        else:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Please specify a dataset type to clean!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

    def create(self,
               release,
               props,
               count=0,
               pkglist=None,
               template=False,
               short=False,
               _uuid=None,
               basejail=False,
               empty=False,
               clone=None,
               skip_batch=False):
        """Creates the jail dataset"""
        count = 0 if count == 1 and not skip_batch else count

        if short and _uuid:
            _uuid = _uuid[:8]

            if len(_uuid) != 8:
                ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        "Need a minimum of 8 characters to use --short"
                        " (-s) and --uuid (-u) together!"
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

        if not template and not release and not empty and not clone:
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    "Must supply either --template (-t) or"
                    " --release (-r)!"
                },
                exit_on_error=self.exit_on_error,
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

            ioc_fetch.IOCFetch(
                release,
                hardened=hardened,
                silent=self.silent,
                exit_on_error=self.exit_on_error).fetch_release()

        if clone:
            clone_uuid, _ = self.__check_jail_existence__()
            status, _ = self.list("jid", uuid=clone_uuid)

            if status:
                ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        f"Jail: {self.jail} must not be running to be"
                        " cloned!"
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

            release = clone_uuid
            clone = self.jail

        try:
            if count > 1 and not skip_batch:
                for j in range(1, count + 1):
                    try:
                        if _uuid is not None:
                            uuid.UUID(_uuid, version=4)

                        count_uuid = _uuid  # Is a UUID
                    except ValueError:
                        # This will allow named jails to use count
                        # This can probably be smarter
                        count_uuid = f"{_uuid}_{j}"

                    self.create(
                        release,
                        props,
                        j,
                        pkglist=pkglist,
                        template=template,
                        short=short,
                        _uuid=count_uuid,
                        basejail=basejail,
                        empty=empty,
                        clone=clone,
                        skip_batch=True)
            else:
                ioc_create.IOCCreate(
                    release,
                    props,
                    count,
                    pkglist,
                    silent=self.silent,
                    template=template,
                    short=short,
                    basejail=basejail,
                    empty=empty,
                    uuid=_uuid,
                    clone=clone,
                    exit_on_error=self.exit_on_error).create_jail()
        except RuntimeError:
            raise

        return False, None

    def destroy_release(self, download=False):
        """Destroy supplied RELEASE and the download dataset if asked"""
        path = f"{self.pool}/iocage/releases/{self.jail}"

        ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Destroying RELEASE dataset: {self.jail}"
            },
            _callback=self.callback,
            silent=self.silent)

        ioc_destroy.IOCDestroy(
            exit_on_error=self.exit_on_error).__destroy_parse_datasets__(
                path, stop=False)

        if download:
            path = f"{self.pool}/iocage/download/{self.jail}"
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message":
                    f"Destroying RELEASE download dataset: {self.jail}"
                },
                _callback=self.callback,
                silent=self.silent)

            ioc_destroy.IOCDestroy(
                exit_on_error=self.exit_on_error).__destroy_parse_datasets__(
                    path, stop=False)

    def destroy_jail(self):
        """
        Destroys the supplied jail, to reduce perfomance hit,
        call IOCage with skip_jails=True
        """
        try:
            self.jails = self.list("uuid")
        except (RuntimeError, SystemExit) as err:
            err = str(err)

            if "Configuration is missing" in err:
                uuid = err.split()[5]
                path = f"{self.pool}/iocage/jails/{uuid}"

                if uuid == self.jail:
                    ioc_destroy.IOCDestroy(exit_on_error=self.exit_on_error
                                           ).__destroy_parse_datasets__(
                                               path, stop=False)

                    ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"{uuid} destroyed"
                        },
                        _callback=self.callback,
                        silent=self.silent)

                    return
                else:
                    ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": err
                        },
                        exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)
        except FileNotFoundError as err:
            # Jail is lacking a configuration, time to nuke it from orbit.
            uuid = str(err).rsplit("/")[-2]
            path = f"{self.pool}/iocage/jails/{uuid}"

            if uuid == self.jail:
                ioc_destroy.IOCDestroy(exit_on_error=self.exit_on_error
                                       ).__destroy_parse_datasets__(path)

                return
            else:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": err
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

        uuid, path = self.__check_jail_existence__()
        status, _ = self.list("jid", uuid=uuid)

        if status:
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f"Stopping {uuid}"
                },
                _callback=self.callback,
                silent=self.silent)

        ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Destroying {uuid}"
            },
            _callback=self.callback,
            silent=self.silent)

        ioc_destroy.IOCDestroy(
            exit_on_error=self.exit_on_error).destroy_jail(path)

    def df(self):
        """Returns a list containing the resource usage of all jails"""
        jail_list = []

        for jail, path in self.jails.items():
            conf = ioc_json.IOCJson(
                path, exit_on_error=self.exit_on_error).json_load()
            mountpoint = f"{self.pool}/iocage/jails/{jail}"

            template = conf["type"]

            if template == "template":
                mountpoint = f"{self.pool}/iocage/templates/{jail}"

            ds = self.zfs.get_dataset(mountpoint)
            zconf = ds.properties

            compressratio = zconf["compressratio"].value
            reservation = zconf["reservation"].value
            quota = zconf["quota"].value
            used = zconf["used"].value
            available = zconf["available"].value

            jail_list.append(
                [jail, compressratio, reservation, quota, used, available])

        return jail_list

    def exec(self,
             command,
             host_user="root",
             jail_user=None,
             console=False,
             pkg=False,
             return_msg=False):
        """Executes a command in the jail as the supplied users."""

        if host_user and jail_user:
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    "Please only specify either host_user or"
                    " jail_user, not both!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        uuid, path = self.__check_jail_existence__()

        if pkg:
            ip4_addr = self.get("ip4_addr")
            ip6_addr = self.get("ip6_addr")
            dhcp = self.get("dhcp")

            if ip4_addr == "none" and ip6_addr == "none" and dhcp != "on":
                ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        "The jail requires an IP address before you "
                        "can use pkg. Set one and restart the jail."
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

            status, jid = self.list("jid", uuid=uuid)

            if not status:
                self.start()
                status, jid = self.list("jid", uuid=uuid)

            command = ["pkg", "-j", jid] + list(command)

        msg, err = ioc_exec.IOCExec(
            command,
            uuid,
            path,
            host_user,
            jail_user,
            console=console,
            silent=self.silent,
            exit_on_error=self.exit_on_error,
            return_msg=return_msg,
            pkg=pkg).exec_jail()

        if not console:
            if err:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": err
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)
            else:
                ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": msg
                    },
                    _callback=self.callback,
                    silent=self.silent)

        if return_msg:
            return msg

    def export(self):
        """Will export a jail"""
        uuid, path = self.__check_jail_existence__()
        status, _ = self.list("jid", uuid=uuid)

        if status:
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    f"{uuid} is runnning, stop the jail before"
                    " exporting!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        ioc_image.IOCImage(exit_on_error=self.exit_on_error).export_jail(
            uuid, path)

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
            ip = [
                x for x in props
                if x.startswith("ip4_addr") or x.startswith("ip6_addr")
            ]

            if not ip and "dhcp=on" not in props:
                ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        "An IP address is needed to fetch a plugin!\n"
                        "Please specify ip(4|6)"
                        "_addr=\"[INTERFACE|]IPADDRESS\"!"
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

            if plugins:
                ioc_fetch.IOCFetch(
                    release,
                    plugin=name,
                    exit_on_error=self.exit_on_error,
                    **kwargs).fetch_plugin_index(
                        props, accept_license=accept)

                return

            if count == 1:
                ioc_fetch.IOCFetch(
                    release, exit_on_error=self.exit_on_error,
                    **kwargs).fetch_plugin(name, props, 0, accept)
            else:
                for j in range(1, count + 1):
                    ioc_fetch.IOCFetch(
                        release, exit_on_error=self.exit_on_error,
                        **kwargs).fetch_plugin(name, props, j, accept)
        else:
            ioc_fetch.IOCFetch(
                release, exit_on_error=self.exit_on_error,
                **kwargs).fetch_release()

    def fstab(self,
              action,
              source,
              destination,
              fstype,
              options,
              dump,
              _pass,
              index=None,
              add_path=False,
              header=False):
        """Adds an fstab entry for a jail"""
        uuid, path = self.__check_jail_existence__()

        if action != "list":
            if add_path:
                destination = f"{self.iocroot}/jails/{uuid}/root{destination}"

            if len(destination) > 88:
                ioc_common.logit(
                    {
                        "level":
                        "WARNING",
                        "message":
                        "The destination's mountpoint exceeds 88 "
                        "characters, this may cause failure!"
                    },
                    _callback=self.callback,
                    silent=self.silent)
        else:
            _fstab_list = []
            index = 0

            with open(f"{self.iocroot}/jails/{uuid}/fstab", "r") as _fstab:
                for line in _fstab.readlines():
                    line = line.rsplit("#")[0].rstrip()
                    _fstab_list.append([index, line.replace("\t", " ")])
                    index += 1

        if action == "list":
            fstab = ioc_fstab.IOCFstab(
                uuid,
                action,
                source,
                destination,
                fstype,
                options,
                dump,
                _pass,
                index=index,
                header=header,
                _fstab_list=_fstab_list,
                exit_on_error=self.exit_on_error).fstab_list()

            return fstab
        else:
            ioc_fstab.IOCFstab(
                uuid,
                action,
                source,
                destination,
                fstype,
                options,
                dump,
                _pass,
                index=index,
                exit_on_error=self.exit_on_error)

    def get(self, prop, recursive=False, plugin=False, pool=False):
        """Get a jail property"""

        if pool:
            return self.pool

        if not recursive:
            if self.jail == "default":
                try:
                    return ioc_json.IOCJson(
                        exit_on_error=self.exit_on_error).json_get_value(
                            prop, default=True)
                except KeyError:
                    ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": f"{prop} is not a valid property!"
                        },
                        exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)

            uuid, path = self.__check_jail_existence__()
            status, jid = self.list("jid", uuid=uuid)

            if prop == "state":
                if status:
                    state = "up"
                else:
                    state = "down"

                return state
            elif plugin:
                _prop = prop.split(".")
                props = ioc_json.IOCJson(
                    path,
                    exit_on_error=self.exit_on_error).json_plugin_get_value(
                        _prop)

                if isinstance(props, dict):
                    return json.dumps(props, indent=4)
                else:
                    return props[0].decode("utf-8")
            elif prop == "all":
                props = ioc_json.IOCJson(
                    path,
                    exit_on_error=self.exit_on_error).json_get_value(prop)

                return props
            else:
                try:
                    return ioc_json.IOCJson(
                        path,
                        exit_on_error=self.exit_on_error).json_get_value(prop)
                except KeyError:
                    ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": f"{prop} is not a valid property!"
                        },
                        exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)
        else:
            jail_list = []

            for uuid, path in self.jails.items():
                try:
                    if prop == "state":
                        status, _ = self.list("jid", uuid=uuid)

                        if status:
                            state = "up"
                        else:
                            state = "down"

                        jail_list.append({uuid: state})
                    elif prop == "all":
                        props = ioc_json.IOCJson(
                            path,
                            exit_on_error=self.exit_on_error).json_get_value(
                                prop)

                        jail_list.append({uuid: props})
                    else:
                        jail_list.append({
                            uuid:
                            ioc_json.IOCJson(
                                path, exit_on_error=self.exit_on_error)
                            .json_get_value(prop)
                        })
                except KeyError:
                    ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": f"{prop} is not a valid property!"
                        },
                        exit_on_error=self.exit_on_error,
                        _callback=self.callback,
                        silent=self.silent)

            return jail_list

    def import_(self):
        """Imports a jail"""
        ioc_image.IOCImage(
            exit_on_error=self.exit_on_error).import_jail(self.jail)

    def list(self,
             lst_type,
             header=False,
             long=False,
             sort="name",
             uuid=None,
             plugin=False,
             quick=False):
        """Returns a list of lst_type"""

        if lst_type == "jid":
            return ioc_list.IOCList().list_get_jid(uuid)

        return ioc_list.IOCList(
            lst_type,
            header,
            long,
            sort,
            plugin=plugin,
            quick=quick,
            exit_on_error=self.exit_on_error).list_datasets()

    def rename(self, new_name):
        uuid, _ = self.__check_jail_existence__()
        path = f"{self.pool}/iocage/jails/{uuid}"
        new_path = path.replace(self.jail, new_name)

        _silent = self.silent
        self.silent = True

        self.stop()
        self.set(f"host_hostuuid={new_name}", rename=True)

        self.silent = _silent

        try:
            # Can't rename when the child is in a non-global zone
            data_dataset = self.zfs.get_dataset(f"{path}/data")
            dependents = data_dataset.dependents

            self.set("jailed=off", zfs=True, zfs_dataset=path)

            for dep in dependents:
                if dep.type != "FILESYSTEM":
                    continue

                d = dep.name
                self.set("jailed=off", zfs=True, zfs_dataset=d)
        except libzfs.ZFSException as err:
            # The dataset doesn't exist, that's OK

            if err.code == libzfs.Error.NOENT:
                pass
            else:
                # Danger, Will Robinson!
                raise

        try:
            self.zfs.get_dataset(path).rename(new_path)
        except libzfs.ZFSException:
            raise

        # Easier.
        su.check_call([
            "zfs", "rename", "-r", f"{self.pool}/iocage@{uuid}", f"@{new_name}"
        ])

        ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Jail: {self.jail} renamed to {new_name}"
            },
            _callback=self.callback,
            silent=self.silent)

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
        uuid, path = self.__check_jail_existence__()
        conf = ioc_json.IOCJson(
            path, silent=self.silent,
            exit_on_error=self.exit_on_error).json_load()
        status, _ = self.list("jid", uuid=uuid)

        if status:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"Please stop {uuid} before trying to"
                    " rollback!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        if conf["template"] == "yes":
            target = f"{self.pool}/iocage/templates/{uuid}"
        else:
            target = f"{self.pool}/iocage/jails/{uuid}"

        try:
            datasets = self.zfs.get_dataset(target)
            self.zfs.get_snapshot(f"{datasets.name}@{name}")
        except libzfs.ZFSException as err:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": err
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        for dataset in datasets.dependents:
            if dataset.type == libzfs.DatasetType.FILESYSTEM:
                self.zfs.get_snapshot(f"{dataset.name}@{name}").rollback()

        # datasets is actually the parent.
        self.zfs.get_snapshot(f"{datasets.name}@{name}").rollback()

        ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Rolled back to: {target}"
            },
            _callback=self.callback,
            silent=self.silent)

    def set(self,
            prop,
            plugin=False,
            rename=False,
            zfs=False,
            zfs_dataset=None):
        """Sets a property for a jail or plugin"""
        # The cli check prevents users changing unwanted properties. We do
        # want to change a protected property with rename, so we disable that.
        cli = False if rename else True

        try:
            key, value = prop.split("=", 1)
        except ValueError:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{prop} is is missing a value!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        if self.jail == "default":
            ioc_json.IOCJson(
                exit_on_error=self.exit_on_error).json_check_default_config()
            default = True
        else:
            default = False

        if default:
            ioc_json.IOCJson(
                self.iocroot, exit_on_error=self.exit_on_error).json_set_value(
                    prop, default=True)

        uuid, path = self.__check_jail_existence__()
        iocjson = ioc_json.IOCJson(
            path,
            cli=cli,
            exit_on_error=self.exit_on_error,
            callback=self.callback,
            silent=self.silent)

        if plugin:
            _prop = prop.split(".")
            iocjson.json_plugin_set_value(_prop)

            return

        if zfs:
            if zfs_dataset is None:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message":
                        "Setting a zfs property requires zfs_dataset."
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

            zfs_key, zfs_value = prop.split("=", 2)
            iocjson.zfs_set_property(zfs_dataset, zfs_key, zfs_value)

            return

        if "template" in key:
            if "templates/" in path and prop != "template=no":
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f"{uuid} is already a template!"
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)
            elif "template" not in path and prop != "template=yes":
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f"{uuid} is already a jail!"
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

        try:
            # We use this to test if it's a valid property at all.
            _prop = prop.partition("=")[0]
            self.get(_prop)

            # The actual setting of the property.
            iocjson.json_set_value(prop)
        except KeyError:
            _prop = prop.partition("=")[0]
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{_prop} is not a valid property!"
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        if key == "ip6_addr":
            rtsold_enable = "YES" if "accept_rtadv" in value else "NO"
            ioc_common.set_rcconf(path, "rtsold_enable", rtsold_enable)

    def snap_list(self, long=True, _sort="created"):
        """Gathers a list of snapshots and returns it"""
        uuid, path = self.__check_jail_existence__()
        conf = ioc_json.IOCJson(
            path, silent=self.silent,
            exit_on_error=self.exit_on_error).json_load()
        snap_list = []
        snap_list_temp = []
        snap_list_root = []

        if conf["template"] == "yes":
            full_path = f"{self.pool}/iocage/templates/{uuid}"
        else:
            full_path = f"{self.pool}/iocage/jails/{uuid}"

        snapshots = self.zfs.get_dataset(full_path)

        for snap in snapshots.snapshots_recursive:
            snap_name = snap.name.rsplit("@")[1] if not long else snap.name
            root_snap_name = snap.name.rsplit("@")[0].split("/")[-1]
            root = False

            if root_snap_name == "root":
                snap_name += "/root"
                root = True
            elif root_snap_name != uuid:
                # basejail datasets.

                continue

            creation = snap.properties["creation"].value
            used = snap.properties["used"].value
            referenced = snap.properties["referenced"].value

            snap_list_temp.append([snap_name, creation, referenced, used]) \
                if not root else snap_list_root.append([snap_name, creation,
                                                        referenced, used])

        for parent in snap_list_temp:
            # We want the /root snapshots immediately after the parent ones
            name = parent[0]

            for root in snap_list_root:
                _name = root[0]

                if f"{name}/root" == _name:
                    snap_list.append(parent)
                    snap_list.append(root)

        sort = ioc_common.ioc_sort("snaplist", _sort, data=snap_list)
        snap_list.sort(key=sort)

        return snap_list

    def snapshot(self, name):
        """Will create a snapshot for the given jail"""
        date = datetime.datetime.utcnow().strftime("%F_%T")
        uuid, path = self.__check_jail_existence__()

        # If they don't supply a snapshot name, we will use the date.

        if not name:
            name = date

        # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
        conf = ioc_json.IOCJson(
            path, silent=self.silent,
            exit_on_error=self.exit_on_error).json_load()

        if conf["template"] == "yes":
            target = f"{self.pool}/iocage/templates/{uuid}"
        else:
            target = f"{self.pool}/iocage/jails/{uuid}"

        dataset = self.zfs.get_dataset(target)

        try:
            dataset.snapshot(f"{target}@{name}", recursive=True)
        except libzfs.ZFSException as err:
            if err.code == libzfs.Error.EXISTS:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": "Snapshot already exists!"
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)
            else:
                raise ()

        ioc_common.logit({
            "level": "INFO",
            "message": f"Snapshot: {target} created."
        })

    def __soft_restart__(self):
        """
        Executes a soft reboot by keeping the jail network stack intact,
        but executing the rc scripts.
        """
        uuid, path = self.__check_jail_existence__()
        status, jid = self.list("jid", uuid=uuid)
        conf = ioc_json.IOCJson(
            path, silent=self.silent,
            exit_on_error=self.exit_on_error).json_load()

        # These need to be a list.
        exec_start = conf["exec_start"].split()
        exec_stop = conf["exec_stop"].split()
        exec_fib = conf["exec_fib"]

        if status:
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f"Soft restarting {uuid} ({self.jail})"
                },
                _callback=self.callback,
                silent=self.silent)

            stop_cmd = [
                "setfib", exec_fib, "jexec", f"ioc-{uuid.replace('.', '_')}"
            ] + exec_stop
            su.Popen(stop_cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

            su.Popen(["pkill", "-j", jid]).communicate()
            start_cmd = [
                "setfib", exec_fib, "jexec", f"ioc-{uuid.replace('.', '_')}"
            ] + exec_start
            su.Popen(start_cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()
            ioc_json.IOCJson(
                path, silent=True, exit_on_error=self.exit_on_error
            ).json_set_value(
                f"last_started={datetime.datetime.utcnow().strftime('%F %T')}")
        else:
            ioc_common.logit(
                {
                    "level": "ERROR",
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
            uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(
                path, silent=self.silent,
                exit_on_error=self.exit_on_error).json_load()
            release = conf["release"].rsplit("-", 1)[0]
            host_release = os.uname()[2].rsplit("-", 1)[0]

            if host_release < release:
                ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        f"\nHost: {host_release} is not greater than"
                        f" jail: {release}\nThis is unsupported."
                    },
                    exit_on_error=self.exit_on_error,
                    _callback=self.callback,
                    silent=self.silent)

            err, msg = self.__check_jail_type__(conf["type"], uuid)
            depends = conf["depends"].split()

            if not err:
                for depend in depends:
                    if depend != "none":
                        self.jail = depend
                        self.start()

                ioc_start.IOCStart(
                    uuid,
                    path,
                    conf,
                    silent=self.silent,
                    callback=self.callback,
                    exit_on_error=self.exit_on_error)

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
            uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(
                path,
                silent=self.silent,
                stop=True,
                exit_on_error=self.exit_on_error).json_load()
            ioc_stop.IOCStop(
                uuid,
                path,
                conf,
                silent=self.silent,
                exit_on_error=self.exit_on_error)
