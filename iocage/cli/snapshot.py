"""snapshot module for the cli."""
from datetime import datetime
from subprocess import CalledProcessError, PIPE, check_call

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_logger import IOCLogger

__cmdname__ = "snapshot_cmd"
__rootcmd__ = True


@click.command(name="snapshot", help="Snapshots the specified jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=False)
def snapshot_cmd(jail, name):
    """Get a list of jails and print the property."""
    lgr = IOCLogger().cli_log()

    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
    date = datetime.utcnow().strftime("%F_%T")

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

    # If they don't supply a snapshot name, we will use the date.
    if not name:
        name = date

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    conf = IOCJson(path).json_load()

    if conf["template"] == "yes":
        target = "{}/iocage/templates/{}@{}".format(pool, tag, name)
    else:
        target = "{}/iocage/jails/{}@{}".format(pool, uuid, name)

    try:
        check_call(["zfs", "snapshot", "-r", target], stderr=PIPE)
        lgr.info("Snapshot: {} created.".format(target))
    except CalledProcessError:
        lgr.critical("Snapshot already exists!")
        exit(1)
