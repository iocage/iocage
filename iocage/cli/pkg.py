"""pkg module for the cli."""
import click

from iocage.lib.ioc_common import logit
from iocage.lib.ioc_exec import IOCExec
from iocage.lib.ioc_list import IOCList

__rootcmd__ = True


@click.command(name="pkg", help="Use pkg inside a specified jail.")
@click.argument("jail", required=True, nargs=1)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def cli(command, jail):
    """Runs pkg with the command given inside the specified jail."""
    jails, paths = IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for t, u in sorted(_jail.items()):
            logit({
                "level"  : "ERROR",
                "message": f"  {u} ({t})"
            })
        exit(1)
    else:
        logit({
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
        exit(1)

    cmd = ("pkg",) + command

    IOCExec(cmd, uuid, tag, path).exec_jail()
