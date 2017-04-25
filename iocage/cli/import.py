"""import module for the cli."""
import click

from iocage.lib.ioc_image import IOCImage
from iocage.lib.ioc_logger import IOCLogger

__cmdname__ = "import_cmd"
__rootcmd__ = True


def callback(message):
    lgr = IOCLogger().cli_log()

    lgr.info(message)


@click.command(name="import", help="Import a specified jail.")
@click.argument("jail", required=True)
def import_cmd(jail):
    """Import from an iocage export."""
    IOCImage(callback=callback).import_jail(jail)
