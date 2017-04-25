"""df module for the cli."""
from subprocess import PIPE, Popen

import click
from texttable import Texttable

import iocage.lib.ioc_common as ioc_common
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_logger import IOCLogger

__cmdname__ = "df_cmd"


@click.command(name="df", help="Show resource usage of all jails.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full uuid.")
@click.option("--sort", "-s", "_sort", default="tag", nargs=1,
              help="Sorts the list by the given type")
def df_cmd(header, _long, _sort):
    """Allows a user to show resource usage of all jails."""
    lgr = IOCLogger().cli_log()

    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
    jail_list = []
    table = Texttable(max_width=0)

    for jail in jails:
        full_uuid = jails[jail]

        if not _long:
            uuid = full_uuid[:8]
        else:
            uuid = full_uuid

        path = paths[jail]
        conf = IOCJson(path).json_load()
        zconf = ["zfs", "get", "-H", "-o", "value"]
        mountpoint = f"{pool}/iocage/jails/{full_uuid}"

        tag = conf["tag"]
        template = conf["type"]

        if template == "template":
            mountpoint = f"{pool}/iocage/templates/{tag}"

        compressratio = Popen(zconf + ["compressratio", mountpoint],
                              stdout=PIPE).communicate()[0].decode(
            "utf-8").strip()
        reservation = Popen(zconf + ["reservation", mountpoint],
                            stdout=PIPE).communicate()[0].decode(
            "utf-8").strip()
        quota = Popen(zconf + ["quota", mountpoint],
                      stdout=PIPE).communicate()[0].decode("utf-8").strip()
        used = Popen(zconf + ["used", mountpoint],
                     stdout=PIPE).communicate()[0].decode("utf-8").strip()
        available = Popen(zconf + ["available", mountpoint],
                          stdout=PIPE).communicate()[0].decode("utf-8").strip()

        jail_list.append([uuid, compressratio, reservation, quota, used,
                          available, tag])

    sort = ioc_common.ioc_sort("df", _sort)
    jail_list.sort(key=sort)
    if header:
        jail_list.insert(0, ["UUID", "CRT", "RES", "QTA", "USE", "AVA", "TAG"])
        # We get an infinite float otherwise.
        table.set_cols_dtype(["t", "t", "t", "t", "t", "t", "t"])
        table.add_rows(jail_list)
        lgr.info(table.draw())
    else:
        for jail in jail_list:
            print("\t".join(jail))
