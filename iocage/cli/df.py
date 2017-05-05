"""df module for the cli."""
import subprocess as su

import click
import texttable

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list


@click.command(name="df", help="Show resource usage of all jails.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full uuid.")
@click.option("--sort", "-s", "_sort", default="tag", nargs=1,
              help="Sorts the list by the given type")
def cli(header, _long, _sort):
    """Allows a user to show resource usage of all jails."""
    jails, paths = ioc_list.IOCList("uuid").list_datasets()
    pool = ioc_json.IOCJson().json_get_value("pool")
    jail_list = []
    table = texttable.Texttable(max_width=0)

    for jail in jails:
        full_uuid = jails[jail]

        if not _long:
            uuid = full_uuid[:8]
        else:
            uuid = full_uuid

        path = paths[jail]
        conf = ioc_json.IOCJson(path).json_load()
        zconf = ["zfs", "get", "-H", "-o", "value"]
        mountpoint = f"{pool}/iocage/jails/{full_uuid}"

        tag = conf["tag"]
        template = conf["type"]

        if template == "template":
            mountpoint = f"{pool}/iocage/templates/{tag}"

        compressratio = su.Popen(zconf + ["compressratio", mountpoint],
                                 stdout=su.PIPE).communicate()[0].decode(
            "utf-8").strip()
        reservation = su.Popen(zconf + ["reservation", mountpoint],
                               stdout=su.PIPE).communicate()[0].decode(
            "utf-8").strip()
        quota = su.Popen(zconf + ["quota", mountpoint],
                         stdout=su.PIPE).communicate()[0].decode(
            "utf-8").strip()
        used = su.Popen(zconf + ["used", mountpoint],
                        stdout=su.PIPE).communicate()[0].decode(
            "utf-8").strip()
        available = su.Popen(zconf + ["available", mountpoint],
                             stdout=su.PIPE).communicate()[0].decode(
            "utf-8").strip()

        jail_list.append([uuid, compressratio, reservation, quota, used,
                          available, tag])

    sort = ioc_common.ioc_sort("df", _sort)
    jail_list.sort(key=sort)
    if header:
        jail_list.insert(0, ["UUID", "CRT", "RES", "QTA", "USE", "AVA", "TAG"])
        # We get an infinite float otherwise.
        table.set_cols_dtype(["t", "t", "t", "t", "t", "t", "t"])
        table.add_rows(jail_list)

        ioc_common.logit({
            "level"  : "INFO",
            "message": table.draw()
        })
    else:
        for jail in jail_list:
            ioc_common.logit({
                "level"  : "INFO",
                "message": "\t".join(jail)
            })
