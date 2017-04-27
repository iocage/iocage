"""migrate module for the cli."""
import fileinput
import os
from shutil import copy
from subprocess import CalledProcessError, STDOUT, check_call

import click

from iocage.lib.ioc_common import checkoutput, copytree, logit
from iocage.lib.ioc_create import IOCCreate
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "migrate_cmd"
__rootcmd__ = True


@click.command(name="migrate",
               help="Migrate all jails to the new jail format.")
@click.option("--force", "-f", is_flag=True, default=False,
              help="Bypass the interactive question.")
@click.option("--delete", "-d", is_flag=True, default=False,
              help="Delete the old dataset after it has been migrated.")
def migrate_cmd(force, delete):
    """Migrates all the iocage_legacy develop basejails to clone jails."""
    jails, paths = IOCList("uuid").list_datasets()

    if not force:
        logit({
            "level"  : "WARNING",
            "message": "\nThis will migrate ALL basejails to clonejails,"
                       " it can take a long time!"
        })

        if not click.confirm("\nAre you sure?"):
            exit()

    for tag, uuid in jails.items():
        pool = IOCJson().json_get_value("pool")
        iocroot = IOCJson(pool).json_get_value("iocroot")
        jail = f"{pool}/iocage/jails/{uuid}"
        jail_old = f"{pool}/iocage/jails_old/{uuid}"
        path = paths[tag]
        conf = IOCJson(path).json_load()
        release = conf["release"]

        if conf["type"] == "basejail":
            try:
                checkoutput(["zfs", "rename", "-p", jail, jail_old],
                            stderr=STDOUT)
            except CalledProcessError as err:
                logit({
                    "level"  : "ERROR",
                    "message": f"{err.output.decode('utf-8').strip()}"
                })
                exit(1)

            try:
                os.remove(f"{iocroot}/tags/{tag}")
            except OSError:
                pass

            new_uuid = IOCCreate(release, "", 0, None, migrate=True,
                                 config=conf,
                                 silent=True).create_jail()
            new_prop = IOCJson(f"{iocroot}/jails/{new_uuid}",
                               silent=True).json_set_value
            new_prop(f"host_hostname={new_uuid}")
            new_prop(f"host_hostuuid={new_uuid}")
            new_prop("type=jail")
            new_prop(f"jail_zfs_dataset={iocroot}/jails/{new_uuid}/data")

            logit({
                "level"  : "INFO",
                "message": "Copying files for {uuid} ({tag}), please wait..."
            })

            copytree(f"{iocroot}/jails_old/{uuid}/root",
                     f"{iocroot}/jails/{new_uuid}/root", symlinks=True)

            copy(f"{iocroot}/jails_old/{uuid}/fstab",
                 f"{iocroot}/jails/{new_uuid}/fstab")
            for line in fileinput.input(f"{iocroot}/jails/{new_uuid}/root/etc/"
                                        "rc.conf", inplace=1):
                logit({
                    "level"  : "INFO",
                    "message": line.replace(f'hostname="{uuid}"',
                                            f'hostname="{new_uuid}"').rstrip()
                })

            if delete:
                try:
                    checkoutput(["zfs", "destroy", "-r", "-f", jail_old],
                                stderr=STDOUT)
                except CalledProcessError as err:
                    raise RuntimeError(
                        f"{err.output.decode('utf-8').rstrip()}")

                try:
                    check_call(["zfs", "destroy", "-r", "-f",
                                f"{pool}/iocage/jails_old"])
                except CalledProcessError:
                    # We just want the top level dataset gone, no big deal.
                    pass

                    logit({
                        "level"  : "INFO",
                        "message": f"{uuid} ({tag}) migrated to {new_uuid}"
                                   f" ({tag})!\n"
                    })
