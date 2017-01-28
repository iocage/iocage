"""df module for the cli."""
import logging
from subprocess import PIPE, Popen

import click
from tabletext import to_text

import iocage.lib.ioc_common as ioc_common
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "df_cmd"


@click.command(name="df", help="Show resource usage of all jails.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full uuid.")
def df_cmd(header, _long):
    """Allows a user to show resource usage of all jails."""
    lgr = logging.getLogger('ioc_cli_df')

    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
    jail_list = []

    for jail in jails:
        full_uuid = jails[jail]

        if not _long:
            uuid = full_uuid[:8]
        else:
            uuid = full_uuid

        path = paths[jail]
        conf = IOCJson(path).load_json()
        zconf = ["zfs", "get", "-H", "-o", "value"]
        mountpoint = "{}/iocage/jails/{}".format(pool, full_uuid)

        tag = conf["tag"]
        compressratio = Popen(zconf + ["compressratio", mountpoint],
                              stdout=PIPE).communicate()[0].strip()
        reservation = Popen(zconf + ["reservation", mountpoint],
                            stdout=PIPE).communicate()[0].strip()
        quota = Popen(zconf + ["quota", mountpoint],
                      stdout=PIPE).communicate()[0].strip()
        used = Popen(zconf + ["used", mountpoint],
                     stdout=PIPE).communicate()[0].strip()
        available = Popen(zconf + ["available", mountpoint],
                          stdout=PIPE).communicate()[0].strip()

        jail_list.append([uuid, compressratio, reservation, quota, used,
                          available, tag])

    jail_list.sort(key=ioc_common.sort_tag)
    if header:
        jail_list.insert(0, ["UUID", "CRT", "RES", "QTA", "USE", "AVA", "TAG"])
        lgr.info(to_text(jail_list, header=True, hor="-", ver="|",
                         corners="+"))
    else:
        for jail in jail_list:
            lgr.info("\t".join(jail))
