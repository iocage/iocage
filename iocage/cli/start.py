"""start module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="start", help="Starts the specified jails or ALL.")
@click.option("--rc", default=False, is_flag=True,
              help="Will start all jails with boot=on, in the specified"
                   " order with smaller value for priority starting first.")
@click.argument("jails", nargs=-1)
def cli(rc, jails):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to start_jail.
    """
    if not jails and not rc:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": 'Usage: iocage start [OPTIONS] JAILS...\n'
                       '\nError: Missing argument "jails".'
        })
        exit(1)

    if rc:
        ioc.IOCage(rc=rc, silent=True).start()
    else:
        for jail in jails:
            ioc.IOCage(jail, rc=rc).start()
