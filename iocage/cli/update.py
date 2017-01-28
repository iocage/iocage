"""Update module for the cli."""

import logging
from subprocess import Popen, check_output

import click

from iocage.lib.ioc_fetch import IOCFetch
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart

__cmdname__ = "update_cmd"
__rootcmd__ = True


@click.command(name="update", help="Run freebsd-update to update a specified "
                                   "jail to the latest patch level.")
@click.argument("jail", required=True)
def update_cmd(jail):
    """Runs update with the command given inside the specified jail."""
    lgr = logging.getLogger('ioc_cli_update')

    jails, paths = IOCList("uuid").list_datasets()
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

    freebsd_version = check_output(["freebsd-version"])
    status, jid = IOCList.list_get_jid(uuid)
    conf = IOCJson(path).load_json()

    if "HBSD" in freebsd_version:
        if conf["type"] == "jail":
            if not status:
                IOCStart(uuid, tag, path, conf, silent=True)
                status, jid = IOCList.list_get_jid(uuid)

            Popen(["hbsd-update", "-j", jid]).communicate()
        elif conf["type"] == "basejail":
            raise RuntimeError("Please run \"iocage migrate\" before trying"
                               " to update {} ({})".format(uuid, tag))
        elif conf["type"] == "template":
            raise RuntimeError("Please convert back to a jail before trying"
                               " to update {} ({})".format(uuid, tag))
        else:
            raise RuntimeError("{} is not a supported jail type.".format(
                conf["type"]
            ))
    else:
        IOCFetch(conf["release"]).update_fetch(True, uuid, tag)
