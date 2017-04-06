"""import module for the cli."""
import click

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_image import IOCImage

__cmdname__ = "import_cmd"
__rootcmd__ = True


def callback(message):
    lgr = ioc_logger.Logger('ioc_cli_import').getLogger()

    lgr.info(message)


@click.command(name="import", help="Import a specified jail.")
@click.argument("jail", required=True)
def import_cmd(jail):
    """Import from an iocage export."""
    IOCImage(callback=callback).import_jail(jail)
