"""destroy module for the cli."""
import click

import iocage.lib.ioc_logger as ioc_logger
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
    lgr = ioc_logger.Logger('ioc_cli_destroy')
    lgr = lgr.getLogger()

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
                IOCDestroy().__destroy_parse_datasets__(path)
                exit()
            else:
                lgr.critical(err)
                exit(1)

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
                    lgr.critical("  {} ({})".format(u, t))
                exit(1)
            else:
                lgr.critical("{} not found!".format(jail))
                exit(1)

            if not force:
                lgr.warning("\nWARNING: This will destroy"
                            " jail {} ({})".format(uuid, tag))

                if not click.confirm("\nAre you sure?"):
                    continue  # no, continue to next jail

            status, _ = get_jid(uuid)

            # If the jail is not running, let's do this thing.
            if status and not force:
                lgr.critical(f"{uuid} ({tag}) is running.\nPlease stop "
                             "it first!")
                exit(1)
            elif status and force:
                lgr.info("Stopping {} ({}).".format(uuid, tag))

            IOCDestroy().destroy_jail(path)
    else:
        lgr.critical("Please specify one or more jails!")
        exit(1)
