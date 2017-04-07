"""start module for the cli."""
import click

import iocage.lib.libiocage as libiocage

__cmdname__ = "start_cmd"
__rootcmd__ = True


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
    libiocage.IOCageMng().mng_jail(rc, jails, 'start')
