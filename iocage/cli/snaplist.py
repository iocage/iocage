"""snaplist module for the cli."""
from subprocess import PIPE, Popen

import click
from texttable import Texttable

from iocage.lib.ioc_common import logit
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


@click.command(name="snaplist", help="Show snapshots of a specified jail.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.argument("jail")
def cli(header, jail):
    """Allows a user to show resource usage of all jails."""
    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
    snap_list = []
    table = Texttable(max_width=0)

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

    conf = IOCJson(path).json_load()

    if conf["template"] == "yes":
        full_path = f"{pool}/iocage/templates/{tag}"
    else:
        full_path = f"{pool}/iocage/jails/{uuid}"

    zconf = ["zfs", "get", "-H", "-o", "value"]
    snapshots = Popen(["zfs", "list", "-r", "-H", "-t", "snapshot",
                       full_path], stdout=PIPE,
                      stderr=PIPE).communicate()[0].decode("utf-8").split("\n")

    for snap in snapshots:
        # We get an empty list at the end.
        if snap:
            snap = snap.split()
            snapname = snap[0].rsplit("@")[1]
            root_snapname = snap[0].rsplit("@")[0].split("/")[-1]

            if root_snapname == "root":
                snapname += "/root"
            elif root_snapname != uuid and root_snapname != tag:
                # basejail datasets.
                continue

            creation = Popen(zconf + ["creation", snap[0]],
                             stdout=PIPE).communicate()[0].decode(
                "utf-8").strip()
            used = snap[1]
            referenced = Popen(zconf + ["referenced", snap[0]],
                               stdout=PIPE).communicate()[0].decode(
                "utf-8").strip()

            snap_list.append([snapname, creation, referenced, used])

    if header:
        snap_list.insert(0, ["NAME", "CREATED", "RSIZE", "USED"])
        # We get an infinite float otherwise.
        table.set_cols_dtype(["t", "t", "t", "t"])
        table.add_rows(snap_list)
        logit({
            "level"  : "INFO",
            "message": table.draw()
        })
    else:
        for snap in snap_list:
            logit({
                "level"  : "INFO",
                "message": "\t".join(snap)
            })
