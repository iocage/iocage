"""migrate module for the cli."""
import fileinput
import os
import shutil
import subprocess as su

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_create as ioc_create
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list

__rootcmd__ = True


@click.command(name="migrate",
               help="Migrate all jails to the new jail format.")
@click.option("--force", "-f", is_flag=True, default=False,
              help="Bypass the interactive question.")
@click.option("--delete", "-d", is_flag=True, default=False,
              help="Delete the old dataset after it has been migrated.")
def cli(force, delete):
    """Migrates all the iocage_legacy develop basejails to clone jails."""
    jails, paths = ioc_list.IOCList("uuid").list_datasets()

    if not force:
        ioc_common.logit({
            "level"  : "WARNING",
            "message": "\nThis will migrate ALL basejails to clonejails,"
                       " it can take a long time!"
        })

        if not click.confirm("\nAre you sure?"):
            exit()

    for tag, uuid in jails.items():
        pool = ioc_json.IOCJson().json_get_value("pool")
        iocroot = ioc_json.IOCJson(pool).json_get_value("iocroot")
        jail = f"{pool}/iocage/jails/{uuid}"
        jail_old = f"{pool}/iocage/jails_old/{uuid}"
        path = paths[tag]
        conf = ioc_json.IOCJson(path).json_load()
        release = conf["release"]

        if conf["type"] == "basejail":
            try:
                ioc_common.checkoutput(["zfs", "rename", "-p", jail, jail_old],
                                       stderr=su.STDOUT)
            except su.CalledProcessError as err:
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"{err.output.decode('utf-8').strip()}"
                })
                exit(1)

            try:
                os.remove(f"{iocroot}/tags/{tag}")
            except OSError:
                pass

            new_uuid = ioc_create.IOCCreate(release, "", 0, None, migrate=True,
                                            config=conf,
                                            silent=True).create_jail()
            new_prop = ioc_json.IOCJson(f"{iocroot}/jails/{new_uuid}",
                                        silent=True).json_set_value
            new_prop(f"host_hostname={new_uuid}")
            new_prop(f"host_hostuuid={new_uuid}")
            new_prop("type=jail")
            new_prop(f"jail_zfs_dataset={iocroot}/jails/{new_uuid}/data")

            ioc_common.logit({
                "level"  : "INFO",
                "message": "Copying files for {uuid} ({tag}), please wait..."
            })

            ioc_common.copytree(f"{iocroot}/jails_old/{uuid}/root",
                                f"{iocroot}/jails/{new_uuid}/root",
                                symlinks=True)

            shutil.copy(f"{iocroot}/jails_old/{uuid}/fstab",
                        f"{iocroot}/jails/{new_uuid}/fstab")
            for line in fileinput.input(f"{iocroot}/jails/{new_uuid}/root/etc/"
                                        "rc.conf", inplace=1):
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": line.replace(f'hostname="{uuid}"',
                                            f'hostname="{new_uuid}"').rstrip()
                })

            if delete:
                try:
                    ioc_common.checkoutput(
                        ["zfs", "destroy", "-r", "-f", jail_old],
                        stderr=su.STDOUT)
                except su.CalledProcessError as err:
                    raise RuntimeError(
                        f"{err.output.decode('utf-8').rstrip()}")

                try:
                    su.check_call(["zfs", "destroy", "-r", "-f",
                                   f"{pool}/iocage/jails_old"])
                except su.CalledProcessError:
                    # We just want the top level dataset gone, no big deal.
                    pass

                    ioc_common.logit({
                        "level"  : "INFO",
                        "message": f"{uuid} ({tag}) migrated to {new_uuid}"
                                   f" ({tag})!\n"
                    })
