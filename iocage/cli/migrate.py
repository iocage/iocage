"""migrate module for the cli."""
from __future__ import print_function
import fileinput
import logging
import os
from shutil import copy
from subprocess import CalledProcessError, STDOUT, check_call, check_output

import click

from iocage.lib.ioc_common import copytree
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
    lgr = logging.getLogger('ioc_cli_migrate')

    jails, paths = IOCList("uuid").list_datasets()

    if not force:
        lgr.warning("\nWARNING: This will migrate ALL basejails, it can take a"
                    " long time!")
        if not click.confirm("\nAre you sure?"):
            exit()

    for tag, uuid in jails.iteritems():
        pool = IOCJson().json_get_value("pool")
        iocroot = IOCJson(pool).json_get_value("iocroot")
        jail = "{}/iocage/jails/{}".format(pool, uuid)
        jail_old = "{}/iocage/jails_old/{}".format(pool, uuid)
        path = paths[tag]
        conf = IOCJson(path).json_load()
        release = conf["release"]

        if conf["type"] == "basejail":
            try:
                check_output(["zfs", "rename", "-p", jail, jail_old],
                             stderr=STDOUT)
            except CalledProcessError as err:
                raise RuntimeError("ERROR: {}".format(err.output.strip()))

            try:
                os.remove("{}/tags/{}".format(iocroot, tag))
            except OSError:
                pass

            new_uuid = IOCCreate(release, "", 0, None, migrate=True,
                                 config=conf,
                                 silent=True).create_jail()
            new_prop = IOCJson("{}/jails/{}".format(iocroot, new_uuid),
                               silent=True).json_set_value
            new_prop("host_hostname={}".format(new_uuid))
            new_prop("host_hostuuid={}".format(new_uuid))
            new_prop("type=jail")
            new_prop(
                "jail_zfs_dataset={}/jails/{}/data".format(iocroot,
                                                           new_uuid))

            lgr.info("Copying files for {} ({}), please wait...".format(
                uuid, tag
            ))

            copytree("{}/jails_old/{}/root".format(iocroot, uuid),
                     "{}/jails/{}/root".format(iocroot, new_uuid),
                     symlinks=True)

            copy("{}/jails_old/{}/fstab".format(iocroot, uuid),
                 "{}/jails/{}/fstab".format(iocroot, new_uuid))
            for line in fileinput.input("{}/jails/{}/root/etc/rc.conf".format(
                    iocroot, new_uuid), inplace=1):
                print(line.replace('hostname="{}"'.format(uuid),
                                   'hostname="{}"'.format(new_uuid)).rstrip())

            if delete:
                try:
                    check_output(["zfs", "destroy", "-r", "-f", jail_old],
                                 stderr=STDOUT)
                except CalledProcessError as err:
                    raise RuntimeError("ERROR: {}".format(err.output.strip()))

                try:
                    check_call(["zfs", "destroy", "-r", "-f",
                                "{}/iocage/jails_old".format(pool)])
                except CalledProcessError:
                    # We just want the top level dataset gone, no big deal.
                    pass

            lgr.info("{} ({}) migrated to {} ({})!\n".format(uuid, tag,
                                                             new_uuid, tag))
