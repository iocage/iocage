"""import module for the cli."""
import click

import iocage.lib.ioc_image as ioc_image

__rootcmd__ = True


@click.command(name="import", help="Import a specified jail.")
@click.argument("jail", required=True)
def cli(jail):
    """Import from an iocage export."""
    ioc_image.IOCImage().import_jail(jail)
