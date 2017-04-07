import libzfs
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_start as ioc_start
import iocage.lib.ioc_list as ioc_list
import iocage.lib.ioc_start as ioc_start
import iocage.lib.ioc_stop as ioc_stop
import iocage.lib.ioc_logger as ioc_logger

from collections import OrderedDict
from operator import itemgetter


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


    def __jail_start__(self, uuid, tag, path):
        conf = ioc_json.IOCJson(path).json_load()

        if conf['type'] in ('jail', 'plugin'):
            ioc_start.IOCStart(uuid, tag, path, conf)
            return (False, None)
        elif conf['type'] == 'basejail':
            return (True, "Please run \"iocage migrate\" before trying to start"
                          f" {uuid} ({tag})")
        elif conf['type'] == 'template':
            return (True, "Please convert back to a jail before trying to start"
                          f" {uuid} ({tag})")
        else:
            return (True, f"{conf['type']} is not a supported jail type.")


    def __jail_stop__(self, uuid, j, path, conf, silent=False):
        ioc_stop.IOCStop(uuid, j, path, conf, silent)

    def mng_jail(self, rc, jails, action):
        if action.lower() not in ('start', 'stop'):
            raise ValueError('You must specify [start|stop] as an action.')

        jail_order = {}
        boot_order = {}

        lgr = ioc_logger.Logger('mng_jail').getLogger()
        _jails, paths = ioc_list.IOCList('uuid').list_datasets()

        _reverse = True if action == 'stop' else False

        for jail_name in _jails:
            path = paths[jail_name]
            conf = ioc_json.IOCJson(path).json_load()
            boot = conf['boot']
            priority = conf['priority']
            jail_order[jail_name] = int(priority)

            # This removes having to grab all the JSON again later.
            if boot == 'on':
                boot_order[jail_name] = int(priority)


            jail_order = OrderedDict(sorted(jail_order.items(),
                                            key=itemgetter(1), reverse=_reverse))
            boot_order = OrderedDict(sorted(boot_order.items(),
                                            key=itemgetter(1), reverse=_reverse))

            if rc:
                for j in boot_order.keys():
                    uuid = _jails[j]
                    path = paths[j]
                    status, _ = ioc_list.IOCList().list_get_jid(uuid)

                    if action == 'stop':
                        if status:
                            lgr.info("  Stopping {} ({})".format(uuid, j))
                            conf = ioc_json.IOCJson(path).json_load()
                            self.__jail_stop__(uuid, j, path, conf, True)
                        else:
                            lgr.info("{} ({}) is not running!".format(uuid, j))
                    elif action == 'start':
                        if not status:
                            err, msg = self.__jail_start__(uuid, j, path)

                            if err:
                                lgr.error(msg)
                        else:
                            lgr.info("{} ({}) is already running!".format(uuid, j))
                exit()

            if len(jails) >= 1 and jails[0] == 'ALL':
                if len(_jails) < 1:
                    lgr.critical(f'No jails exist to {action}')
                    exit(1)

                for j in jail_order:
                    uuid = _jails[j]
                    path = paths[j]
                    if action == 'stop':
                        conf = ioc_json.IOCJson(path).json_load()
                        self.__jail_stop__(uuid, j, path, conf, True)
                    elif action == 'start':
                        err, msg = self.__jail_start__(uuid, j, path)

                        if err:
                            lgr.error(msg)
            else:
                if len(jails) < 1:
                    lgr.critical("Please specify either one or more jails or ALL!")
                    exit(1)

                for jail in jails:
                    _jail = {tag: uuid for (tag, uuid) in _jails.items() if
                             uuid.startswith(jail) or tag == jail}

                    if len(_jail) == 1:
                        tag, uuid = next(iter(_jail.items()))
                        path = paths[tag]
                    elif len(_jail) > 1:
                        lgr.error("Multiple jails found for"
                                  " {}:".format(jail))
                        for t, u in sorted(_jail.items()):
                            lgr.critical("  {} ({})".format(u, t))
                        exit(1)
                    else:
                        lgr.critical("{} not found!".format(jail))
                        exit(1)


                    if action == 'start':
                        err, msg = self.__jail_start__(uuid, tag, path)

                        if err:
                            lgr.critical(msg)
                            exit(1)
                    elif action == 'stop':
                        conf = ioc_json.IOCJson(path).json_load()
                        self.__jail_stop__(uuid, tag, path, conf)
