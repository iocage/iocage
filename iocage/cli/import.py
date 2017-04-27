"""import module for the cli."""
import click

from iocage.lib.ioc_image import IOCImage

__cmdname__ = "import_cmd"
__rootcmd__ = True


@click.command(name="import", help="Import a specified jail.")
@click.argument("jail", required=True)
def import_cmd(jail):
    """Import from an iocage export."""
    IOCImage().import_jail(jail)
