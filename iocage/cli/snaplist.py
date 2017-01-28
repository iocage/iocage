"""Snaplist module for the cli."""
import logging
from subprocess import PIPE, Popen

import click
from tabletext import to_text

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "snaplist_cmd"


@click.command(name="snaplist", help="Show snapshots of a specified jail.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.argument("jail")
def snaplist_cmd(header, jail):
    """Allows a user to show resource usage of all jails."""
    lgr = logging.getLogger('ioc_cli_snaplist')

    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
    snap_list = []

    _jail = {tag: uuid for (tag, uuid) in jails.iteritems() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(_jail.iteritems())
        path = paths[tag]
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.iteritems()):
            lgr.error("  {} ({})".format(u, t))
        raise RuntimeError()
    else:
        raise RuntimeError("{} not found!".format(jail))

    full_path = "{}{}".format(pool, path)
    zconf = ["zfs", "get", "-H", "-o", "value"]
    snapshots = Popen(["zfs", "list", "-H", "-t", "snapshot", "-d",
                       "1", full_path], stdout=PIPE,
                      stderr=PIPE).communicate()[0].split("\n")

    for snap in snapshots:
        # We get an empty list at the end.
        if snap:
            snap = snap.split()
            snapname = snap[0].rsplit("@")[1]

            creation = Popen(zconf + ["creation", snap[0]],
                             stdout=PIPE).communicate()[0].strip()
            used = snap[1]
            referenced = Popen(zconf + ["referenced", snap[0]],
                               stdout=PIPE).communicate()[0].strip()

            snap_list.append([snapname, creation, referenced, used])

    if header:
        snap_list.insert(0, ["NAME", "CREATED", "RSIZE", "USED"])
        lgr.info(to_text(snap_list, header=True, hor="-", ver="|",
                         corners="+"))
    else:
        for snap in snap_list:
            lgr.info("\t".join(snap))
