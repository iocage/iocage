"""snapremove module for the cli."""
import logging
from subprocess import CalledProcessError, check_call

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "snapremove_cmd"


@click.command(name="snapremove", help="Remove specified snapshot of a jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=True)
def snapremove_cmd(jail, name):
    """Removes a snapshot from a user supplied jail."""
    lgr = logging.getLogger('ioc_cli_snapremove')

    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")
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
        lgr.error("ERROR: {}".format(err))
