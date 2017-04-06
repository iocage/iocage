"""export module for the cli."""
import click

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_image import IOCImage
from iocage.lib.ioc_list import IOCList

__cmdname__ = "export_cmd"
__rootcmd__ = True

lgr = ioc_logger.Logger("ioc_cli_export").getLogger()


def callback(message):
    lgr.info(message)


@click.command(name="export", help="Exports a specified jail.")
@click.argument("jail", required=True)
def export_cmd(jail):
    """Make a recursive snapshot of the jail and export to a file."""
    jails, paths = IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.items()):
            lgr.error("  {} ({})".format(u, t))
        raise RuntimeError()
    else:
        lgr.critical("{} not found!".format(jail))
        exit(1)

    status, _ = IOCList().list_get_jid(uuid)
    if status:
        lgr.critical("{} ({}) is runnning, stop the jail before "
                     "exporting!".format(uuid, tag))
        exit(1)

    IOCImage(callback=callback).export_jail(uuid, tag, path)
