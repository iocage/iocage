"""destroy module for the cli."""
import logging

import click

from iocage.lib.ioc_destroy import IOCDestroy
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "destroy_cmd"
__rootcmd__ = True


@click.command(name="destroy", help="Destroy specified jail(s).")
@click.option("--force", "-f", default=False, is_flag=True)
@click.argument("jails", nargs=-1)
def destroy_cmd(force, jails):
    """Destroys the jail's 2 datasets and the snapshot from the RELEASE."""
    lgr = logging.getLogger('ioc_cli_destroy')

    if jails:
        get_jid = IOCList().list_get_jid

        try:
            jail_list, paths = IOCList("uuid").list_datasets()
        except RuntimeError as err:
            err = str(err)

            if "Configuration is missing" in err:
                uuid = err.split()[6]
                pool = IOCJson().json_get_value("pool")
                path = f"{pool}/iocage/jails/{uuid}"

                IOCDestroy().__stop_jails__(path.replace(pool, ""))
                IOCDestroy().__destroy_datasets__(path)
                exit()
            else:
                raise RuntimeError(err)

        for jail in jails:
            _jail = {tag: uuid for (tag, uuid) in jail_list.items() if
                     uuid.startswith(jail) or tag == jail}

            if len(_jail) == 1:
                tag, uuid = next(iter(_jail.items()))
                path = paths[tag]
            elif len(_jail) > 1:
                lgr.error("Multiple jails found for"
                          " {}:".format(jail))
                for t, u in sorted(_jail.items()):
                    lgr.error("  {} ({})".format(u, t))
                raise RuntimeError()
            else:
                raise RuntimeError("{} not found!".format(jail))

            if not force:
                lgr.warning("\nWARNING: This will destroy"
                            " jail {} ({})".format(uuid, tag))

                if not click.confirm("\nAre you sure?"):
                    continue  # no, continue to next jail

            status, _ = get_jid(uuid)

            # If the jail is not running, let's do this thing.
            if status and not force:
                raise RuntimeError(f"{uuid} ({tag}) is running.\nPlease stop "
                                   "it first!")
            elif status and force:
                lgr.info("Stopping {} ({}).".format(uuid, tag))

            IOCDestroy().destroy_jail(path)
    else:
        raise RuntimeError("Please specify one or more jails!")
