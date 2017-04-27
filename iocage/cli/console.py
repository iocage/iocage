"""console module for the cli."""
from subprocess import Popen

import click

from iocage.lib.ioc_common import logit
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart

__cmdname__ = "console_cmd"
__rootcmd__ = True


@click.command(name="console", help="Login to a jail.")
@click.argument("jail")
@click.option("--force", "-f", default=False, is_flag=True)
def console_cmd(jail, force):
    """
    Runs jexec to login into the specified jail. Accepts a force flag that
    will attempt to start the jail if it is not already running.
    """
    jails, paths = IOCList("uuid").list_datasets()

    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]

        iocjson = IOCJson(path)
        conf = iocjson.json_load()
        login_flags = conf["login_flags"].split()
        exec_fib = conf["exec_fib"]
        status, _ = IOCList().list_get_jid(uuid)
    elif len(_jail) > 1:
        logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}"
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
            "message": f" {jail} not found!"
        })
        exit(1)

    if not status and not force:
        logit({
            "level"  : "ERROR",
            "message": f"{uuid} ({tag}) is not running!"
        })
        exit(1)

    if not status and force:
        logit({
            "level"  : "INFO",
            "message": f"{uuid} ({tag}) is not running, starting jail."
        })
        if conf["type"] == "jail":
            IOCStart(uuid, jail, path, conf, silent=True)
            status = True
        elif conf["type"] == "basejail":
            logit({
                "level"  : "ERROR",
                "message": "Please run \"iocage migrate\" before trying to"
                           " start {uuid} ({tag})"
            })
            exit(1)
        elif conf["type"] == "template":
            logit({
                "level"  : "ERROR",
                "message": "Please convert back to a jail before to start"
                           f" {uuid} ({tag})"
            })
            exit(1)
        else:
            logit({
                "level"  : "ERROR",
                "message": f"{conf['type']} is not a supported jail type."
            })
            exit(1)

    if status:
        Popen(["setfib", exec_fib, "jexec", f"ioc-{uuid}", "login"] +
              login_flags).communicate()
