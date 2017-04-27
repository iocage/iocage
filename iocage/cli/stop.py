"""stop module for the cli."""
import click

from iocage.lib.ioc_common import logit
from iocage.lib.iocage import IOCage

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
    if not jails and not rc:
        logit({
            "level"  : "ERROR",
            "message": 'Usage: iocage stop [OPTIONS] JAILS...\n'
                       '\nError: Missing argument "jails".'
        })
        exit(1)

    if rc:
        IOCage(rc=rc, silent=True).start()
    else:
        for jail in jails:
            IOCage(jail, rc=rc).stop()
