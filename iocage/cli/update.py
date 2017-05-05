"""update module for the cli."""
import subprocess as su

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_fetch as ioc_fetch
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list
import iocage.lib.ioc_start as ioc_start
import iocage.lib.ioc_stop as ioc_stop

__rootcmd__ = True


@click.command(name="update", help="Run freebsd-update to update a specified "
                                   "jail to the latest patch level.")
@click.argument("jail", required=True)
def cli(jail):
    """Runs update with the command given inside the specified jail."""
    jails, paths = ioc_list.IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for t, u in sorted(_jail.items()):
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"  {u} ({t})"
            })
        exit(1)
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
        exit(1)

    freebsd_version = ioc_common.checkoutput(["freebsd-version"])
    status, jid = ioc_list.IOCList.list_get_jid(uuid)
    conf = ioc_json.IOCJson(path).json_load()
    started = False

    if conf["type"] == "jail":
        if not status:
            ioc_start.IOCStart(uuid, tag, path, conf, silent=True)
            status, jid = ioc_list.IOCList.list_get_jid(uuid)
            started = True
    elif conf["type"] == "basejail":
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please run \"iocage migrate\" before trying"
                       f" to update {uuid} ({tag})"
        })
        exit(1)
    elif conf["type"] == "template":
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please convert back to a jail before trying"
                       f" to update {uuid} ({tag})"
        })
        exit(1)
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{conf['type']} is not a supported jail type."
        })
        exit(1)

    if "HBSD" in freebsd_version:
        su.Popen(["hbsd-update", "-j", jid]).communicate()

        if started:
            ioc_stop.IOCStop(uuid, tag, path, conf, silent=True)
    else:
        ioc_fetch.IOCFetch(conf["cloned_release"]).fetch_update(True, uuid,
                                                                tag)

        if started:
            ioc_stop.IOCStop(uuid, tag, path, conf, silent=True)
