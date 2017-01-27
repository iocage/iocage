"""Stop module for the cli."""
import logging

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_stop import IOCStop

__cmdname__ = "stop_cmd"
__rootcmd__ = True


@click.command(name="stop", help="Stops the specified jails or ALL.")
@click.argument("jails", nargs=-1)
def stop_cmd(jails):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail.
    """
    lgr = logging.getLogger('ioc_cli_stop')

    _jails, paths = IOCList("uuid").get_datasets()

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
