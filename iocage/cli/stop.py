"""Stop module for the cli."""
import logging
from collections import OrderedDict
from operator import itemgetter

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_stop import IOCStop

__cmdname__ = "stop_cmd"
__rootcmd__ = True


@click.command(name="stop", help="Stops the specified jails or ALL.")
@click.option("--rc", default=False, is_flag=True,
              help="Will stop all jails with boot=on, in the specified"
                   " order with higher value for priority stopping first.")
@click.argument("jails", nargs=-1)
def stop_cmd(rc, jails):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail.
    """
    lgr = logging.getLogger('ioc_cli_stop')

    _jails, paths = IOCList("uuid").list_datasets()

    if rc:
        boot_order = {}
        for j in _jails:
            path = paths[j]
            conf = IOCJson(path).load_json()
            boot = conf["boot"]
            priority = conf["priority"]

            if boot == "on":
                boot_order[j] = int(priority)

        boot_order = OrderedDict(sorted(boot_order.iteritems(),
                                        key=itemgetter(1), reverse=True))
        for j in boot_order.iterkeys():
            uuid = _jails[j]
            path = paths[j]
            conf = IOCJson(path).load_json()
            status, _ = IOCList().list_get_jid(uuid)

            if status:
                lgr.info("  Stopping {} ({})".format(uuid, j))
                IOCStop(uuid, j, path, conf, silent=True)
            else:
                lgr.info("{} ({}) is not running!".format(uuid, j))
        exit()
    if jails[0] == "ALL":
        for j in _jails:
            uuid = _jails[j]
            path = paths[j]

            conf = IOCJson(path).load_json()
            IOCStop(uuid, j, path, conf)
    else:
        for jail in jails:
            _jail = {tag: uuid for (tag, uuid) in _jails.iteritems() if
                     uuid.startswith(jail) or tag == jail}

            if len(_jail) == 1:
                tag, uuid = next(_jail.iteritems())
                path = paths[tag]
            elif len(_jail) > 1:
                lgr.error("Multiple jails found for"
                          " {}:".format(jail))
                for t, u in sorted(_jail.iteritems()):
                    lgr.error("  {} ({})".format(u, t))
                raise RuntimeError()
            else:
                raise RuntimeError("{} not found!".format(jail))

            conf = IOCJson(path).load_json()
            IOCStop(uuid, tag, path, conf)
