"""restart module for the cli."""
import datetime
import subprocess as su

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list
import iocage.lib.ioc_start as ioc_start
import iocage.lib.ioc_stop as ioc_stop

__rootcmd__ = True


def check_type(uuid, tag, path, _all, soft):
    """
    Checks the jail type and spits out an error or does the specified 
    restart method.
    """
    conf = ioc_json.IOCJson(path).json_load()

    if conf["type"] in ("jail", "plugin"):
        if not soft:
            __hard_restart__(uuid, tag, path, conf)
        else:
            __soft_restart__(uuid, tag, path, conf)
    elif conf["type"] == "basejail":
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please run \"iocage migrate\" before trying"
                       f" to restart {uuid} ({tag})"
        })
        if not _all:
            exit(1)
    elif conf["type"] == "template":
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please convert back to a jail before trying"
                       f" to restart {uuid} ({tag})"
        })
        if not _all:
            exit(1)
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{conf['type']} is not a supported jail type."
        })

        if not _all:
            exit(1)


@click.command(name="restart", help="Restarts the specified jails or ALL.")
@click.option("--soft", "-s", help="Restarts the jail but does not tear"
                                   " down the network stack.", is_flag=True)
@click.argument("jail")
def cli(jail, soft):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail and start_jail.
    """
    jails, paths = ioc_list.IOCList("uuid").list_datasets()

    if jail == "ALL":
        for j in jails:
            uuid = jails[j]
            path = paths[j]

            check_type(uuid, j, path, True, soft)
    else:
        _jail = {tag: uuid for (tag, uuid) in jails.items() if
                 uuid.startswith(jail) or tag == jail}

        if len(_jail) == 1:
            tag, uuid = next(iter(_jail.items()))
            path = paths[tag]

            check_type(uuid, tag, path, False, soft)
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


def __hard_restart__(uuid, jail, path, conf):
    """Stops and then starts the jail."""
    ioc_stop.IOCStop(uuid, jail, path, conf)
    ioc_start.IOCStart(uuid, jail, path, conf)


def __soft_restart__(uuid, jail, path, conf):
    """
    Will tear down the jail by running exec_stop and then exec_start, leaving
    the network stack intact, ideal for VIMAGE.
    """
    getjid = ioc_list.IOCList().list_get_jid(uuid)
    status, jid = getjid

    # These needs to be a list.
    exec_start = conf["exec_start"].split()
    exec_stop = conf["exec_stop"].split()
    exec_fib = conf["exec_fib"]

    if status:
        ioc_common.logit({
            "level"  : "INFO",
            "message": f"Soft restarting {uuid} ({jail})"
        })
        stop_cmd = ["setfib", exec_fib, "jexec", f"ioc-{uuid}"] + exec_stop
        su.Popen(stop_cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

        su.Popen(["pkill", "-j", jid]).communicate()
        start_cmd = ["setfib", exec_fib, "jexec", f"ioc-{uuid}"] + exec_start
        su.Popen(start_cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()
        ioc_json.IOCJson(path, silent=True).json_set_value(
            "last_started={}".format(
                datetime.datetime.utcnow().strftime("%F %T")))
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{jail} is not running!"
        })
        exit(1)
