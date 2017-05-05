"""export module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_image as ioc_image
import iocage.lib.ioc_list as ioc_list

__rootcmd__ = True


@click.command(name="export", help="Exports a specified jail.")
@click.argument("jail", required=True)
def cli(jail):
    """Make a recursive snapshot of the jail and export to a file."""
    jails, paths = ioc_list.IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:

        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for t, u in sorted(_jail.items()):
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"  {u} ({t})"
            })
        exit(1)
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
        exit(1)

    status, _ = ioc_list.IOCList().list_get_jid(uuid)
    if status:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{uuid} ({tag}) is runnning, stop the jail before"
                       " exporting!"
        })
        exit(1)

    ioc_image.IOCImage().export_jail(uuid, tag, path)
