from collections import OrderedDict
from operator import itemgetter

import libzfs

import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list
import iocage.lib.ioc_logger as ioc_logger
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
        __types = {'all': '/iocage/jails', 'base': '/iocage/releases',
                   'template': '/iocage/templates', 'uuid': '/iocage/jails',
                   'root': '/iocage',
                  }
        if option_type in __types.keys():
            return self.zfs.get_dataset(f"{self.pool}{__types[option_type]}").children

    def get_iocroot(self):
        """
        Helper to get the iocroot.

        Return:
                string: with the iocroot name.
        """
        return ioc_json.IOCJson(self.pool).json_get_value("iocroot")


class IOCageMng(object):
    """Parent class to manage a jails lifecycle."""

    def __init__(self):
        self.jails, self.paths = ioc_list.IOCList("uuid").list_datasets()

    def __check_jail_existence__(self, jail):
        """
        Helper to check if jail dataset exists
        Return: 
                tuple: The jails tag, uuid, path
        """
        _jail = {tag: uuid for (tag, uuid) in self.jails.items() if
                 uuid.startswith(jail) or tag == jail}

        if len(_jail) == 1:
            tag, uuid = next(iter(_jail.items()))
            path = self.paths[tag]

            return tag, uuid, path
        elif len(_jail) > 1:
            raise RuntimeError("Multiple jails found for {}:".format(jail))
        else:
            raise RuntimeError("{} not found!".format(jail))

    def __check_jail_type__(self, conf, uuid, tag):
        """
        Return: 
            tuple: True if error with a message, or False/None
        """
        if conf['type'] in ('jail', 'plugin'):
            return False, None
        elif conf['type'] == 'basejail':
            return (True, "Please run \"iocage migrate\" before trying to"
                          f" start {uuid} ({tag})")
        elif conf['type'] == 'template':
            return (True, "Please convert back to a jail before trying to"
                          f" start {uuid} ({tag})")
        else:
            return True, f"{conf['type']} is not a supported jail type."

    def __jail_start__(self, jail, silent=False):
        """Checks jails type and existence, then starts the jail"""
        tag, uuid, path = self.__check_jail_existence__(jail)
        conf = ioc_json.IOCJson(path).json_load()
        err, msg = self.__check_jail_type__(conf, uuid, tag)

        if not err:
            ioc_start.IOCStart(uuid, tag, path, conf, silent)

            return False, None
        else:
            return err, msg

    def __jail_stop__(self, jail, silent=False):
        """Stops the jail."""
        tag, uuid, path = self.__check_jail_existence__(jail)
        conf = ioc_json.IOCJson(path).json_load()
        ioc_stop.IOCStop(uuid, tag, path, conf, silent)

    def mng_jail(self, rc, jails, action):
        """Starts and stops jails."""
        if action.lower() not in ('start', 'stop'):
            raise ValueError('You must specify [start|stop] as an action.')

        jail_order = {}
        boot_order = {}

        lgr = ioc_logger.Logger('mng_jail').getLogger()
        _reverse = True if action == 'stop' else False
        jails = self.jails if rc else jails

        if len(jails) < 1:
            lgr.critical("Please specify either one or more jails or"
                         "ALL!")
            exit(1)
        else:
            for jail in jails:
                tag, uuid, path = self.__check_jail_existence__(jail)
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

                if rc:
                    for j in boot_order.keys():
                        tag, uuid, path = self.__check_jail_existence__(j)
                        status, _ = ioc_list.IOCList().list_get_jid(uuid)

                        if action == 'stop':
                            if status:
                                lgr.info("  Stopping {} ({})".format(uuid, j))
                                self.__jail_stop__(j, True)
                            else:
                                lgr.info("{} ({}) is not running!".format(uuid, j))
                        elif action == 'start':
                            if not status:
                                err, msg = self.__jail_start__(j)

                                if err:
                                    lgr.error(msg)
                            else:
                                lgr.info("{} ({}) is already running!".format(j))
                    exit()

                if len(jails) >= 1 and jails[0] == 'ALL':
                    for j in jail_order:
                        if action == 'stop':
                            self.__jail_stop__(j, True)
                        elif action == 'start':
                            err, msg = self.__jail_start__(j)

                            if err:
                                lgr.error(msg)
                else:
                    if action == 'start':
                        err, msg = self.__jail_start__(jail)

                        if err and msg:
                            lgr.critical(msg)
                            exit(1)
                    elif action == 'stop':
                        self.__jail_stop__(jail)
