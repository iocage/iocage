"""snapremove module for the cli."""
from subprocess import CalledProcessError, check_call

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_logger import IOCLogger

__cmdname__ = "snapremove_cmd"


@click.command(name="snapremove", help="Remove specified snapshot of a jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=True)
def snapremove_cmd(jail, name):
    """Removes a snapshot from a user supplied jail."""
    lgr = IOCLogger().cli_log()

    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.items()):
            lgr.critical("  {} ({})".format(u, t))
        exit(1)
    else:
        lgr.critical("{} not found!".format(jail))
        exit(1)

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    conf = IOCJson(path).json_load()

    if conf["template"] == "yes":
        target = "{}/iocage/templates/{}@{}".format(pool, tag, name)
    else:
        target = "{}/iocage/jails/{}@{}".format(pool, uuid, name)

    try:
        check_call(["zfs", "destroy", "-r", "-f", target])
        lgr.info("Snapshot: {} destroyed.".format(target))
    except CalledProcessError as err:
        lgr.error("{}".format(err))
