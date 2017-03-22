"""start module for the cli."""
from collections import OrderedDict
from operator import itemgetter

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart
import iocage.lib.ioc_log as ioc_log

__cmdname__ = "start_cmd"
__rootcmd__ = True


def start_jail(uuid, tag, path):
    """
    Will do a few jail type checks and then start the jail.

    :param uuid: The jails UUID
    :param tag: The jails tag
    :param path: The path to the JSON configuration file
    :type uuid: string
    :type tag: string
    :type path: string
    :return: A tuple (True/False, Message) True if an error has occured.
    """
    conf = IOCJson(path).json_load()

    if conf["type"] in ("jail", "plugin"):
        IOCStart(uuid, tag, path, conf)

        return False, None
    elif conf["type"] == "basejail":
        return(True, "Please run \"iocage migrate\" before trying to start"
                     f" {uuid} ({tag})")
    elif conf["type"] == "template":
        return(True, "Please convert back to a jail before trying to start"
                     f" {uuid} ({tag})")
    else:
        return True, f"{conf['type']} is not a supported jail type."


@click.command(name="start", help="Starts the specified jails or ALL.")
@click.option("--rc", default=False, is_flag=True,
              help="Will start all jails with boot=on, in the specified"
                   " order with smaller value for priority starting first.")
@click.argument("jails", nargs=-1)
def start_cmd(rc, jails):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to start_jail.
    """
    lgr = ioc_log.getLogger('ioc_cli_start')

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
                                    key=itemgetter(1)))
    boot_order = OrderedDict(sorted(boot_order.items(),
                                    key=itemgetter(1)))
    if rc:
        for j in boot_order.keys():
            uuid = _jails[j]
            path = paths[j]
            status, _ = IOCList().list_get_jid(uuid)

            if not status:
                err, msg = start_jail(uuid, j, path)

                if err:
                    lgr.error(msg)
            else:
                lgr.info("{} ({}) is already running!".format(uuid, j))
        exit()

    if len(jails) >= 1 and jails[0] == "ALL":
        if len(_jails) < 1:
            raise RuntimeError("No jails exist to start!")

        for j in jail_order:
            uuid = _jails[j]
            path = paths[j]
            err, msg = start_jail(uuid, j, path)

            if err:
                lgr.error(msg)
    else:
        if len(jails) < 1:
            raise RuntimeError("Please specify either one or more jails or "
                               "ALL!")

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
                raise RuntimeError("{} not found!".format(jail))

            err, msg = start_jail(uuid, tag, path)

            if err:
                raise RuntimeError(msg)
