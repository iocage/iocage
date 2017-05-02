"""import module for the cli."""
import click

from iocage.lib.ioc_image import IOCImage

__rootcmd__ = True


@click.command(name="import", help="Import a specified jail.")
@click.argument("jail", required=True)
def cli(jail):
    """Import from an iocage export."""
    IOCImage().import_jail(jail)
