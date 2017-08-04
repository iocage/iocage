# Copyright (c) 2014-2017, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""migrate module for the cli."""
import datetime
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
    # TODO: Move to API
    jails = ioc_list.IOCList("uuid").list_datasets()

    if not force:
        ioc_common.logit({
            "level"  : "WARNING",
            "message": "\nThis will migrate ALL iocage-legacy develop"
                       " basejails to clonejails, it can take a long"
                       " time!\nPlease make sure you are not running"
                       " this on iocage-legacy 1.7.6 basejails."
        })

        if not click.confirm("\nAre you sure?"):
            exit()

    for uuid, path in jails.items():
        pool = ioc_json.IOCJson().json_get_value("pool")
        iocroot = ioc_json.IOCJson(pool).json_get_value("iocroot")
        jail = f"{pool}/iocage/jails/{uuid}"
        jail_old = f"{pool}/iocage/jails_old/{uuid}"
        conf = ioc_json.IOCJson(path).json_load()

        try:
            tag = conf["tag"]
        except KeyError:
            # These are actually NEW jails.
            continue

        release = conf["cloned_release"]

        if conf["type"] == "basejail":
            try:
                ioc_common.checkoutput(["zfs", "rename", "-p", jail, jail_old],
                                       stderr=su.STDOUT)
            except su.CalledProcessError as err:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": f"{err.output.decode('utf-8').strip()}"
                }, exit_on_error=True)

            try:
                os.remove(f"{iocroot}/tags/{tag}")
            except OSError:
                pass

            date_fmt_legacy = "%Y-%m-%d@%H:%M:%S"

            # We don't want to rename datasets to a bunch of dates.
            try:
                datetime.datetime.strptime(tag, date_fmt_legacy)
                _name = str(uuid.uuid4())
            except ValueError:
                # They already named this jail, making it like our new ones.
                _name = tag

            new_uuid = ioc_create.IOCCreate(release, "", 0, None, migrate=True,
                                            config=conf, silent=True,
                                            uuid=_name,
                                            exit_on_error=True).create_jail()
            new_prop = ioc_json.IOCJson(f"{iocroot}/jails/{new_uuid}",
                                        silent=True).json_set_value
            new_prop(f"host_hostname={new_uuid}")
            new_prop(f"host_hostuuid={new_uuid}")
            new_prop("type=jail")
            new_prop(f"jail_zfs_dataset={iocroot}/jails/{new_uuid}/data")

            ioc_common.logit({
                "level"  : "INFO",
                "message": f"Copying files for {new_uuid}, please wait..."
            })

            ioc_common.copytree(f"{iocroot}/jails_old/{uuid}/root",
                                f"{iocroot}/jails/{new_uuid}/root",
                                symlinks=True)

            shutil.copy(f"{iocroot}/jails_old/{uuid}/fstab",
                        f"{iocroot}/jails/{new_uuid}/fstab")
            for line in fileinput.input(f"{iocroot}/jails/{new_uuid}/root/etc/"
                                        "rc.conf", inplace=1):
                print(line.replace(f'hostname="{uuid}"',
                                   f'hostname="{new_uuid}"').rstrip())

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
                "message": f"{uuid} ({tag}) migrated to {new_uuid}!\n"
            })
