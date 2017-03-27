"""pkg module for the cli."""
import click

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_exec import IOCExec
from iocage.lib.ioc_list import IOCList

__cmdname__ = "pkg_cmd"
__rootcmd__ = True


@click.command(name="pkg", help="Use pkg inside a specified jail.")
@click.argument("jail", required=True, nargs=1)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def pkg_cmd(command, jail):
    """Runs pkg with the command given inside the specified jail."""
    lgr = ioc_logger.Logger('ioc_cli_pkg')
    lgr = lgr.getLogger()

    jails, paths = IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
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

    cmd = ("pkg",) + command

    IOCExec(cmd, uuid, tag, path).exec_jail()
