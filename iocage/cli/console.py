"""console module for the cli."""

import click

import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="console", help="Login to a jail.")
@click.argument("jail")
def cli(jail):
    """
    Runs jexec to login into the specified jail.
    """
    # Command is empty since this command is hardcoded later on.
    ioc.IOCage(jail).exec("", console=True)
