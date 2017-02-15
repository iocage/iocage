"""pkg module for the cli."""
import logging

import click

from iocage.lib.ioc_exec import IOCExec
from iocage.lib.ioc_list import IOCList

__cmdname__ = "pkg_cmd"
__rootcmd__ = True


@click.command(name="pkg", help="Use pkg inside a specified jail.")
@click.argument("jail", required=True, nargs=1)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def pkg_cmd(command, jail):
    """Runs pkg with the command given inside the specified jail."""
    lgr = logging.getLogger('ioc_cli_pkg')

    jails, paths = IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.iteritems() if
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

    cmd = ("pkg",) + command

    IOCExec(cmd, uuid, tag, path).exec_jail()
