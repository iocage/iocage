"""upgrade module for the cli."""
import click

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart
from iocage.lib.ioc_stop import IOCStop
from iocage.lib.ioc_upgrade import IOCUpgrade

__cmdname__ = "upgrade_cmd"
__rootcmd__ = True


@click.command(name="upgrade", help="Run freebsd-update to upgrade a specified"
                                    " jail to the RELEASE given.")
@click.argument("jail", required=True)
@click.option("--release", "-r", required=True, help="RELEASE to upgrade to")
def upgrade_cmd(jail, release):
    """Runs upgrade with the command given inside the specified jail."""
    lgr = ioc_logger.Logger('ioc_cli_upgrade')
    lgr = lgr.getLogger()

    jails, paths = IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
        root_path = "{}/root".format(path)
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.items()):
            lgr.critical("  {} ({})".format(u, t))
        exit(1)
    else:
        lgr.critical("{} not found!".format(jail))
        exit(1)

    status, jid = IOCList.list_get_jid(uuid)
    conf = IOCJson(path).json_load()
    jail_release = conf["release"]
    started = False

    if conf["release"] == "EMPTY":
        lgr.critical("Upgrading is not supported for empty jails.")
        exit(1)
    if conf["type"] == "jail":
        if not status:
            IOCStart(uuid, tag, path, conf, silent=True)
            started = True

            new_release = IOCUpgrade(conf, release, root_path).upgrade_jail()
    elif conf["type"] == "basejail":
        lgr.critical("Please run \"iocage migrate\" before trying"
                     " to upgrade {} ({})".format(uuid, tag))
        exit(1)
    elif conf["type"] == "template":
        lgr.critical("Please convert back to a jail before trying"
                     " to upgrade {} ({})".format(uuid, tag))
        exit(1)
    else:
        lgr.critical("{} is not a supported jail type.".format(conf["type"]))
        exit(1)

    if started:
        IOCStop(uuid, tag, path, conf, silent=True)

    lgr.info(f"\n{uuid} ({tag}) successfully upgraded from {jail_release} to"
             f" {new_release}!")
