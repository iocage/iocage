"""destroy module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

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
    pool = ioc.PoolAndDataset().get_pool()
    iocage = ioc.IOCage(skip_jails=True)

    if download and not release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "--release (-r) must be specified as well!"
        })

    if jails and not release:
        try:
            jail_list, paths = ioc.IOCage.list("uuid")
        except RuntimeError as err:
            err = str(err)

            if "Configuration is missing" in err:
                uuid = err.split()[5]
                path = f"{pool}/iocage/jails/{uuid}"

                if uuid == jails[0]:
                    iocage.destroy(path, parse=True)
                    exit()
                else:
                    ioc_common.logit({
                        "level"  : "EXCEPTION",
                        "message": err
                    })
            else:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": err
                })
        except FileNotFoundError as err:
            # Jail is lacking a configuration, time to nuke it from orbit.
            uuid = str(err).rsplit("/")[-2]
            path = f"{pool}/iocage/jails/{uuid}"

            if uuid == jails[0]:
                iocage.destroy(path, parse=True)
                exit()
            else:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": err
                })

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
                    "level"  : "EXCEPTION",
                    "message": f"{jail} not found!"
                })

            if not force:
                ioc_common.logit({
                    "level"  : "WARNING",
                    "message": f"\nThis will destroy jail {uuid} ({tag})"
                })

                if not click.confirm("\nAre you sure?"):
                    continue  # no, continue to next jail

            status, _ = ioc.IOCage().list("jid", uuid=uuid)

            # If the jail is not running, let's do this thing.
            if status and not force:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": f"{uuid} ({tag}) is running.\nPlease stop"
                               " it first!"
                })
            elif status and force:
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"Stopping {uuid} ({tag})."
                })

            iocage.destroy(path)
    elif jails and release:
        iocage = ioc.IOCage(skip_jails=True)

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

            iocage.destroy(path, parse=True)

            if download:
                path = f"{pool}/iocage/download/{release}"
                iocage.destroy(path, parse=True)

    elif not jails and release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify one or more RELEASEs!"
        })
    else:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify one or more jails!"
        })
