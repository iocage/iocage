"""restart module for the cli."""
from datetime import datetime
from subprocess import PIPE, Popen

import click

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart
from iocage.lib.ioc_stop import IOCStop

__cmdname__ = "restart_cmd"
__rootcmd__ = True

lgr = ioc_logger.Logger('ioc_cli_restart').getLogger()


def check_type(uuid, tag, path, _all, soft):
    """
    Checks the jail type and spits out an error or does the specified 
    restart method.
    """
    conf = IOCJson(path).json_load()

    if conf["type"] in ("jail", "plugin"):
        if not soft:
            __hard_restart__(uuid, tag, path, conf)
        else:
            __soft_restart__(uuid, tag, path, conf)
    elif conf["type"] == "basejail":
        lgr.critical("Please run \"iocage migrate\" before trying"
                     f" to restart {uuid} ({tag})")
        if not _all:
            exit(1)
    elif conf["type"] == "template":
        lgr.critical("Please convert back to a jail before trying"
                     f" to restart {uuid} ({tag})")
        if not _all:
            exit(1)
    else:
        lgr.critical(f"{conf['type']} is not a supported jail type.")

        if not _all:
            exit(1)


@click.command(name="restart", help="Restarts the specified jails or ALL.")
@click.option("--soft", "-s", help="Restarts the jail but does not tear"
                                   " down the network stack.", is_flag=True)
@click.argument("jail")
def restart_cmd(jail, soft):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail and start_jail.
    """
    jails, paths = IOCList("uuid").list_datasets()

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
            lgr.error("Multiple jails found for"
                      " {}:".format(jail))
            for t, u in sorted(_jail.items()):
                lgr.error("  {} ({})".format(u, t))
            raise RuntimeError()
        else:
            lgr.critical("{} not found!".format(jail))
            exit(1)


def __hard_restart__(uuid, jail, path, conf):
    """Stops and then starts the jail."""
    IOCStop(uuid, jail, path, conf)
    IOCStart(uuid, jail, path, conf)


def __soft_restart__(uuid, jail, path, conf):
    """
    Will tear down the jail by running exec_stop and then exec_start, leaving
    the network stack intact, ideal for VIMAGE.
    """
    getjid = IOCList().list_get_jid(uuid)
    status, jid = getjid
    lgr = ioc_logger.Logger('ioc_cli_restart').getLogger()

    # These needs to be a list.
    exec_start = conf["exec_start"].split()
    exec_stop = conf["exec_stop"].split()
    exec_fib = conf["exec_fib"]

    if status:
        lgr.info("Soft restarting {} ({})".format(uuid, jail))
        stop_cmd = ["setfib", exec_fib, "jexec", f"ioc-{uuid}"] + exec_stop
        Popen(stop_cmd, stdout=PIPE, stderr=PIPE).communicate()

        Popen(["pkill", "-j", jid]).communicate()
        start_cmd = ["setfib", exec_fib, "jexec", f"ioc-{uuid}"] + exec_start
        Popen(start_cmd, stdout=PIPE, stderr=PIPE).communicate()
        IOCJson(path, silent=True).json_set_value("last_started={}".format(
            datetime.utcnow().strftime("%F %T")))
    else:
        lgr.critical("{} is not running!".format(jail))
        exit(1)
