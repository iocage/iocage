"""Update module for the cli."""

import logging

import click

from iocage.lib.ioc_fetch import IOCFetch
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "update_cmd"
__rootcmd__ = True


@click.command(name="update", help="Run freebsd-update inside a specified "
                                   "jail.")
@click.argument("jail", required=True, nargs=1)
def update_cmd(jail):
    """Runs update with the command given inside the specified jail."""
    lgr = logging.getLogger('ioc_cli_update')

    jails, paths = IOCList("uuid").get_datasets()
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

    conf = IOCJson(path).load_json()
    IOCFetch(conf["release"]).update_fetch(True, uuid, tag)
