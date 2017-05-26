"""destroy module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_destroy as ioc_destroy
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list

__rootcmd__ = True


@click.command(name="destroy", help="Destroy specified jail(s).")
@click.option("--force", "-f", default=False, is_flag=True)
@click.option("--release", "-r", default=False, is_flag=True)
@click.option("--download", "-d", default=False, is_flag=True,
              help="Delete the download dataset of the specified RELEASE as"
                   " well.")
@click.argument("jails", nargs=-1)
def cli(force, release, download, jails):
    """Destroys the jail's 2 datasets and the snapshot from the RELEASE."""
    if download and not release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "--release (-r) must be specified as well!"
        })

    if jails and not release:
        get_jid = ioc_list.IOCList().list_get_jid

        try:
            jail_list, paths = ioc_list.IOCList("uuid").list_datasets()
        except RuntimeError as err:
            err = str(err)

            if "Configuration is missing" in err:
                uuid = err.split()[5]
                pool = ioc_json.IOCJson().json_get_value("pool")
                path = f"{pool}/iocage/jails/{uuid}"

                ioc_destroy.IOCDestroy().__stop_jails__(path.replace(pool, ""))
                ioc_destroy.IOCDestroy().__destroy_parse_datasets__(path)
                exit()
            else:
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": err
                })
                exit(1)

        for jail in jails:
            _jail = {tag: uuid for (tag, uuid) in jail_list.items() if
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

            if not force:
                ioc_common.logit({
                    "level"  : "WARNING",
                    "message": f"\nThis will destroy jail {uuid} ({tag})"
                })

                if not click.confirm("\nAre you sure?"):
                    continue  # no, continue to next jail

            status, _ = get_jid(uuid)

            # If the jail is not running, let's do this thing.
            if status and not force:
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"{uuid} ({tag}) is running.\nPlease stop"
                               " it first!"
                })
                exit(1)
            elif status and force:
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"Stopping {uuid} ({tag})."
                })

            ioc_destroy.IOCDestroy().destroy_jail(path)
    elif jails and release:
        pool = ioc_json.IOCJson().json_get_value("pool")

        for release in jails:
            path = f"{pool}/iocage/releases/{release}"

            if not force:
                ioc_common.logit({
                    "level"  : "WARNING",
                    "message": f"\nThis will destroy RELEASE: {release} and "
                               "any jail that was created with it."
                })

                if not click.confirm("\nAre you sure?"):
                    continue

            ioc_destroy.IOCDestroy().__destroy_parse_datasets__(path)

            if download:
                path = f"{pool}/iocage/download/{release}"
                ioc_destroy.IOCDestroy().__destroy_parse_datasets__(path)

    elif not jails and release:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please specify one or more RELEASEs!"
        })
        exit(1)
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please specify one or more jails!"
        })
        exit(1)
