"""Restart module for the cli."""
import logging
from datetime import datetime
from subprocess import PIPE, Popen

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart
from iocage.lib.ioc_stop import IOCStop

__cmdname__ = "restart_cmd"
__rootcmd__ = True


@click.command(name="restart", help="Restarts the specified jails or ALL.")
@click.option("--soft", "-s", help="Restarts the jail but does not tear"
                                   " down the network stack.", is_flag=True)
@click.argument("jail")
def restart_cmd(jail, soft):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail and start_jail.
    """
    lgr = logging.getLogger('ioc_cli_restart')

    jails, paths = IOCList("uuid").get_datasets()
    if jail == "ALL":
        for j in jails:
            uuid = jails[j]
            path = paths[j]

            conf = IOCJson(path).load_json()

            if conf["type"] == "jail":
                try:
                    if not soft:
                        __hard_restart(uuid, j, path, conf)
                    else:
                        __soft_restart(uuid, j, path, conf)
                except RuntimeError as err:
                    lgr.error(err)
            elif conf["type"] == "basejail":
                lgr.error("Please run \"iocage migrate\" before trying"
                          " to restart {} ({})".format(uuid, j))
            elif conf["type"] == "template":
                raise RuntimeError("Please convert back to a jail before trying"
                                   " to restart {} ({})".format(uuid, j))
            else:
                lgr.error("{} is not a supported jail type.".format(
                    conf["type"]
                ))
    else:
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

        if conf["type"] == "jail":
            if not soft:
                __hard_restart(uuid, tag, path, conf)
            else:
                __soft_restart(uuid, tag, path, conf)
        elif conf["type"] == "basejail":
            raise RuntimeError("Please run \"iocage migrate\" before trying"
                               " to restart {} ({})".format(uuid, tag))
        elif conf["type"] == "template":
            raise RuntimeError("Please convert back to a jail before trying"
                               " to restart {} ({})".format(uuid, tag))
        else:
            raise RuntimeError("{} is not a supported jail type.".format(
                conf["type"]
            ))


def __hard_restart(uuid, jail, path, conf):
    """Stops and then starts the jail."""
    IOCStop(uuid, jail, path, conf)
    IOCStart(uuid, path).start_jail(jail, conf)


def __soft_restart(uuid, jail, path, conf):
    """
    Will tear down the jail by running exec_stop and then exec_start, leaving
    the network stack intact, ideal for VIMAGE.
    """
    getjid = IOCList().get_jid(uuid)
    status, jid = getjid
    lgr = logging.getLogger('ioc_cli_restart')

    # These needs to be a list.
    exec_start = conf["exec_start"].split()
    exec_stop = conf["exec_stop"].split()

    if status:
        lgr.info("Soft restarting {} ({})".format(uuid, jail))
        stop_cmd = ["jexec", "ioc-{}".format(uuid)] + exec_stop
        Popen(stop_cmd, stdout=PIPE, stderr=PIPE).communicate()

        Popen(["pkill", "-j", jid]).communicate()
        start_cmd = ["jexec", "ioc-{}".format(uuid)] + exec_start
        Popen(start_cmd, stdout=PIPE, stderr=PIPE).communicate()
        IOCJson(path).set_prop_value("last_started={}".format(
            datetime.utcnow().strftime("%F %T")), silent=True)
    else:
        raise RuntimeError("{} is not running!".format(jail))
