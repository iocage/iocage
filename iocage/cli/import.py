"""import module for the cli."""
import click

import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="import", help="Import a specified jail.")
@click.argument("jail", required=True)
def cli(jail):
    """Import from an iocage export."""
    ioc.IOCage(jail).import_()
