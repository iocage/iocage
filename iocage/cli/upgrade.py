"""upgrade module for the cli."""
import logging
import os
from subprocess import PIPE, Popen, check_output

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart
from iocage.lib.ioc_stop import IOCStop

__cmdname__ = "upgrade_cmd"
__rootcmd__ = True


@click.command(name="upgrade", help="Run freebsd-update to upgrade a specified"
                                    " jail to the RELEASE given.")
@click.argument("jail", required=True)
@click.option("--release", "-r", required=True, help="RELEASE to upgrade to")
def upgrade_cmd(jail, release):
    """Runs upgrade with the command given inside the specified jail."""
    lgr = logging.getLogger('ioc_cli_upgrade')

    jails, paths = IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.iteritems() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(_jail.iteritems())
        path = paths[tag]
        root_path = "{}/root".format(path)
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.iteritems()):
            lgr.error("  {} ({})".format(u, t))
        raise RuntimeError()
    else:
        raise RuntimeError("{} not found!".format(jail))

    pool = IOCJson().json_get_value("pool")
    iocroot = IOCJson(pool).json_get_value("iocroot")
    freebsd_version = check_output(["freebsd-version"])
    status, jid = IOCList.list_get_jid(uuid)
    conf = IOCJson(path).json_load()
    host_release = os.uname()[2]
    jail_release = conf["release"]
    started = False

    if conf["type"] == "jail":
        if not status:
            IOCStart(uuid, tag, path, conf, silent=True)
            status, jid = IOCList.list_get_jid(uuid)
            started = True
    elif conf["type"] == "basejail":
        raise RuntimeError("Please run \"iocage migrate\" before trying"
                           " to upgrade {} ({})".format(uuid, tag))
    elif conf["type"] == "template":
        raise RuntimeError("Please convert back to a jail before trying"
                           " to upgrade {} ({})".format(uuid, tag))
    else:
        raise RuntimeError("{} is not a supported jail type.".format(
            conf["type"]
        ))

    _freebsd_version = "{}/releases/{}/root/bin/freebsd-version".format(
        iocroot, release)

    if "HBSD" in freebsd_version:
        Popen(["hbsd-upgrade", "-j", jid]).communicate()
    else:
        if os.path.isfile("{}/etc/freebsd-update.conf".format(root_path)):
            # 10.3-RELEASE and under lack this flag
            if float(host_release.partition("-")[0][:5]) <= 10.3:
                raise RuntimeError("Host: {} is too old, please upgrade to "
                                   "10.3-RELEASE or above".format(
                    host_release))

            os.environ["PAGER"] = "/bin/cat"
            fetch = Popen(["freebsd-update", "-b", root_path, "-d",
                           "{}/var/db/freebsd-update/".format(root_path), "-f",
                           "{}/etc/freebsd-update.conf".format(root_path),
                           "--currently-running {}".format(jail_release), "-r",
                           release, "upgrade"], stdin=PIPE)
            fetch.communicate("y")

            while not __upgrade_install__(root_path, release):
                pass

            if release[:4].endswith("-"):
                # 9.3-RELEASE and under don't actually have this binary.
                new_release = release
            else:
                with open(_freebsd_version, "r") as r:
                    for line in r:
                        if line.startswith("USERLAND_VERSION"):
                            new_release = line.rstrip().partition("=")[2].strip(
                                '"')

            IOCJson(path, silent=True).json_set_value("release={}".format(
                new_release))

            if started:
                IOCStop(uuid, tag, path, conf, silent=True)

            lgr.info("\n{} ({}) successfully upgraded from {} to {}!".format(
                uuid, tag, jail_release, new_release))


def __upgrade_install__(path, release):
    """Installs the upgrade and returns the exit code."""
    install = Popen(["freebsd-update", "-b", path, "-d",
                     "{}/var/db/freebsd-update/".format(path), "-f",
                     "{}/etc/freebsd-update.conf".format(path), "-r",
                     release, "install"], stderr=PIPE)
    install.communicate()

    return install.returncode
