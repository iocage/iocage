import collections
import operator
import os
import subprocess as su

import libzfs

import iocage.lib.ioc_clean as ioc_clean
import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_create as ioc_create
import iocage.lib.ioc_fetch as ioc_fetch
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
                 activate=False):
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

        if not activate:
            self.pool = PoolAndDataset().get_pool()
            self.iocroot = PoolAndDataset().get_iocroot()
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
            msg = f"Multiple jails found for {self.jail}:"

            for j in sorted(_jail.items()):
                msg += f"\n  {j}"

            raise RuntimeError(msg)
        else:
            raise RuntimeError(f"{self.jail} not found!")

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
            return

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
            ioc_clean.IOCClean().clean_jails()
            ioc_common.logit({
                "level"  : "INFO",
                "message": "All iocage jail datasets have been destroyed."
            },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "all":
            ioc_clean.IOCClean().clean_all()
            ioc_common.logit({
                "level"  : "INFO",
                "message": "All iocage datasets have been destroyed."
            },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "release":
            ioc_clean.IOCClean().clean_releases()
            ioc_common.logit({
                "level"  : "INFO",
                "message": "All iocage RELEASE and jail datasets have been"
                           " destroyed."
            },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == "template":
            ioc_clean.IOCClean().clean_templates()
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
               clone=None):
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

            ioc_fetch.IOCFetch(release, hardened=hardened).fetch_release()

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
            ioc_create.IOCCreate(release, props, count, pkglist,
                                 template=template, short=short, uuid=uuid,
                                 basejail=basejail, empty=empty, clone=clone
                                 ).create_jail()
        except RuntimeError as err:
            return True, err

        return False, None

    @staticmethod
    def list(lst_type, header=False, long=False, sort="tag", uuid=None):
        """Returns a list of lst_type"""
        if lst_type == "jid":
            return ioc_list.IOCList().list_get_jid(uuid)

        return ioc_list.IOCList(lst_type, header, long, sort).list_datasets()

    def start(self, jail=None):
        """Checks jails type and existence, then starts the jail"""
        if self.rc or self._all:
            if not jail:
                self.__jail_order__("start")
        else:
            tag, uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(path).json_load()
            err, msg = self.__check_jail_type__(conf["type"], uuid, tag)

            if not err:
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
            conf = ioc_json.IOCJson(path).json_load()
            ioc_stop.IOCStop(uuid, tag, path, conf, silent=self.silent)
