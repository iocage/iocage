"""Snapshot module for the cli"""
import logging
from datetime import datetime
from subprocess import CalledProcessError, check_call

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "snapshot_cmd"
__rootcmd__ = True


@click.command(name="snapshot", help="Snapshots the specified jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=False)
def snapshot_cmd(jail, name):
    """Get a list of jails and print the property."""
    lgr = logging.getLogger('ioc_cli_snapshot')

    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
    date = datetime.utcnow().strftime("%F_%T")

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

    # If they don't supply a snapshot name, we will use the date.
    if not name:
        name = date

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    target = "{}{}@{}".format(pool, path, name)

    try:
        check_call(["zfs", "snapshot", "-r", target])
        lgr.info("Snapshot: {} created.".format(target))
    except CalledProcessError as err:
        lgr.error("ERROR: {}".format(err))
