"""stop module for the cli."""
from collections import OrderedDict
from operator import itemgetter

import click

import iocage.lib.ioc_logger as ioc_logger
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
    lgr = ioc_logger.Logger('ioc_cli_stop')
    lgr = lgr.getLogger()

    _jails, paths = IOCList("uuid").list_datasets()
    jail_order = {}
    boot_order = {}

    for j in _jails:
        path = paths[j]
        conf = IOCJson(path).json_load()
        boot = conf["boot"]
        priority = conf["priority"]

        jail_order[j] = int(priority)

        # This removes having to grab all the JSON again later.
        if boot == "on":
            boot_order[j] = int(priority)

    jail_order = OrderedDict(sorted(jail_order.items(),
                                    key=itemgetter(1), reverse=True) )
    boot_order = OrderedDict(sorted(boot_order.items(),
                                    key=itemgetter(1), reverse=True))
    if rc:
        for j in boot_order.keys():
            uuid = _jails[j]
            path = paths[j]
            conf = IOCJson(path).json_load()
            status, _ = IOCList().list_get_jid(uuid)

            if status:
                lgr.info("  Stopping {} ({})".format(uuid, j))
                IOCStop(uuid, j, path, conf, silent=True)
            else:
                lgr.info("{} ({}) is not running!".format(uuid, j))
        exit()

    if len(jails) >= 1 and jails[0] == "ALL":
        if len(_jails) < 1:
            lgr.error("No jails exist to stop!")
            exit(1)

        for j in jail_order:
            uuid = _jails[j]
            path = paths[j]

            conf = IOCJson(path).json_load()
            IOCStop(uuid, j, path, conf)
    else:
        if len(jails) < 1:
            lgr.warning("Please specify either one or more jails or ALL!")
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
                    lgr.error("  {} ({})".format(u, t))
                raise RuntimeError()
            else:
                lgr.critical("{} not found!".format(jail))
                exit(1)

            conf = IOCJson(path).json_load()
            IOCStop(uuid, tag, path, conf)
