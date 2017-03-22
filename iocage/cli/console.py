"""console module for the cli."""
from subprocess import Popen

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart
import iocage.lib.ioc_log as ioc_log

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
    lgr = ioc_log.getLogger('ioc_cli_console')
    # TODO: setfib support
    jails, paths = IOCList("uuid").list_datasets()

    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]

        iocjson = IOCJson(path)
        conf = iocjson.json_load()
        login_flags = conf["login_flags"].split()
        status, _ = IOCList().list_get_jid(uuid)
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.items()):
            lgr.error("  {} ({})".format(u, t))
        raise RuntimeError()
    else:
        raise RuntimeError("{} not found!".format(jail))

    if not status and not force:
        raise RuntimeError("{} ({}) is not running!".format(uuid, tag))

    if not status and force:
        lgr.info("{} ({}) is not running".format(uuid, tag) +
                 ", starting jail.")
        if conf["type"] == "jail":
            IOCStart(uuid, jail, path, conf, silent=True)
            status = True
        elif conf["type"] == "basejail":
            raise RuntimeError("Please run \"iocage migrate\" before trying"
                               " to start {} ({})".format(uuid, tag))
        elif conf["type"] == "template":
            raise RuntimeError("Please convert back to a jail before trying"
                               " to start {} ({})".format(uuid, tag))
        else:
            raise RuntimeError("{} is not a supported jail type.".format(
                conf["type"]
            ))

    if status:
        Popen(["jexec", "ioc-{}".format(uuid), "login"] +
              login_flags).communicate()
