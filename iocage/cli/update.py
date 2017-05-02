"""update module for the cli."""
from subprocess import Popen

import click

from iocage.lib.ioc_common import checkoutput, logit
from iocage.lib.ioc_fetch import IOCFetch
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart
from iocage.lib.ioc_stop import IOCStop

__rootcmd__ = True


@click.command(name="update", help="Run freebsd-update to update a specified "
                                   "jail to the latest patch level.")
@click.argument("jail", required=True)
def cli(jail):
    """Runs update with the command given inside the specified jail."""
    jails, paths = IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for t, u in sorted(_jail.items()):
            logit({
                "level"  : "ERROR",
                "message": f"  {u} ({t})"
            })
        exit(1)
    else:
        logit({
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
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
        logit({
            "level"  : "ERROR",
            "message": "Please run \"iocage migrate\" before trying"
                       f" to update {uuid} ({tag})"
        })
        exit(1)
    elif conf["type"] == "template":
        logit({
            "level"  : "ERROR",
            "message": "Please convert back to a jail before trying"
                       f" to update {uuid} ({tag})"
        })
        exit(1)
    else:
        logit({
            "level"  : "ERROR",
            "message": f"{conf['type']} is not a supported jail type."
        })
        exit(1)

    if "HBSD" in freebsd_version:
        Popen(["hbsd-update", "-j", jid]).communicate()

        if started:
            IOCStop(uuid, tag, path, conf, silent=True)
    else:
        IOCFetch(conf["cloned_release"]).fetch_update(True, uuid, tag)

        if started:
            IOCStop(uuid, tag, path, conf, silent=True)
