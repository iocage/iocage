"""update module for the cli."""
from subprocess import Popen

import click

from iocage.lib.ioc_common import checkoutput
from iocage.lib.ioc_fetch import IOCFetch
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_logger import IOCLogger
from iocage.lib.ioc_start import IOCStart
from iocage.lib.ioc_stop import IOCStop

__cmdname__ = "update_cmd"
__rootcmd__ = True


@click.command(name="update", help="Run freebsd-update to update a specified "
                                   "jail to the latest patch level.")
@click.argument("jail", required=True)
def update_cmd(jail):
    """Runs update with the command given inside the specified jail."""
    lgr = IOCLogger().cli_log()

    jails, paths = IOCList("uuid").list_datasets()
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

    freebsd_version = checkoutput(["freebsd-version"])
    status, jid = IOCList.list_get_jid(uuid)
    conf = IOCJson(path).json_load()
    started = False

    if conf["type"] == "jail":
        if not status:
            IOCStart(uuid, tag, path, conf, silent=True)
            status, jid = IOCList.list_get_jid(uuid)
            started = True
    elif conf["type"] == "basejail":
        lgr.critical("Please run \"iocage migrate\" before trying"
                     " to update {} ({})".format(uuid, tag))
        exit(1)
    elif conf["type"] == "template":
        lgr.critical("Please convert back to a jail before trying"
                     " to update {} ({})".format(uuid, tag))
        exit(1)
    else:
        lgr.critical("{} is not a supported jail type.".format(conf["type"]))
        exit(1)

    if "HBSD" in freebsd_version:
        Popen(["hbsd-update", "-j", jid]).communicate()

        if started:
            IOCStop(uuid, tag, path, conf, silent=True)
    else:
        IOCFetch(conf["cloned_release"]).fetch_update(True, uuid, tag)

        if started:
            IOCStop(uuid, tag, path, conf, silent=True)
