from collections import OrderedDict
from operator import itemgetter

import libzfs

import iocage.lib.ioc_common as ioc_common
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
    def __init__(self, jail=None, rc=False, callback=None, silent=False):
        self.pool = PoolAndDataset().get_pool()
        self.iocroot = PoolAndDataset().get_iocroot()
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.jails, self._paths = self.list("uuid")
        self.jail = jail
        self.rc = rc
        self._all = True if self.jail and 'ALL' in self.jail else False
        self.callback = ioc_common.callback if not callback else callback
        self.silent = silent

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

    def __check_jail_type__(self, _type, uuid, tag):
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

    def list(self, lst_type, header=False, long=False, sort="tag", uuid=None):
        """foo"""
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

            jail_order = OrderedDict(sorted(jail_order.items(),
                                            key=itemgetter(1),
                                            reverse=_reverse))
            boot_order = OrderedDict(sorted(boot_order.items(),
                                            key=itemgetter(1),
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
