"""snapremove module for the cli."""
from subprocess import CalledProcessError, check_call

import click

from iocage.lib.ioc_common import logit
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "snapremove_cmd"


@click.command(name="snapremove", help="Remove specified snapshot of a jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=True)
def snapremove_cmd(jail, name):
    """Removes a snapshot from a user supplied jail."""
    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for t, u in sorted(_jail.items()):
            logit({
                "level"  : "ERROR",
                "message": f"  {u} ({t})"
            })
        exit(1)
    else:
        logit({
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
        exit(1)

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    conf = IOCJson(path).json_load()

    if conf["template"] == "yes":
        target = f"{pool}/iocage/templates/{tag}@{name}"
    else:
        target = f"{pool}/iocage/jails/{uuid}@{name}"

    try:
        check_call(["zfs", "destroy", "-r", "-f", target])
        logit({
            "level"  : "INFO",
            "message": f"Snapshot: {target} destroyed."
        })
    except CalledProcessError as err:
        logit({
            "level"  : "ERROR",
            "message": f"{err}"
        })
        exit(1)
