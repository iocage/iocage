"""stop module for the cli."""
import click

import iocage.lib.libiocage as libiocage

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
    libiocage.IOCageMng(callback=True).mng_jail(rc, jails, 'stop')
