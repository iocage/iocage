"""CLI command to destroy a jail."""
import logging

import click

from iocage.lib.ioc_destroy import IOCDestroy
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_stop import IOCStop

__cmdname__ = "destroy_cmd"
__rootcmd__ = True


@click.command(name="destroy", help="Destroy specified jail(s).")
@click.option("--force", "-f", default=False, is_flag=True)
@click.argument("jails", nargs=-1)
def destroy_cmd(force, jails):
    """Destroys the jail's 2 datasets and the snapshot from the RELEASE."""
    lgr = logging.getLogger('ioc_cli_destroy')

    if jails:
        get_jid = IOCList().get_jid
        jail_list, paths = IOCList("uuid").get_datasets()

        for jail in jails:
            _jail = {tag: uuid for (tag, uuid) in jail_list.iteritems() if
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

            if not force:
                lgr.warning("\nWARNING: This will destroy"
                            " jail {} ({})".format(uuid, tag))
                lgr.info("Dataset: {}".format(path))

                if not click.confirm("\nAre you sure?"):
                    continue # no, continue to next jail

            status, _ = get_jid(uuid)

            # If the jail is not running, let's do this thing.
            if status and not force:
                raise RuntimeError("{} ({}) is running."
                                   " Please stop it first!".format(uuid, tag))
            elif status and force:
                conf = IOCJson(path).load_json()
                lgr.info("Stopping {} ({}).".format(uuid, tag))
                IOCStop(uuid, tag, path, conf, silent=True)

            IOCDestroy(uuid, tag, path).destroy_jail()
    else:
        raise RuntimeError("Please specify one or more jails!")
