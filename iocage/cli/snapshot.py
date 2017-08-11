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
"""snapshot module for the cli."""
import datetime
import subprocess as su

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list

__rootcmd__ = True


@click.command(name="snapshot", help="Snapshots the specified jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=False)
def cli(jail, name):
    """Get a list of jails and print the property."""
    # TODO: Move to API
    jails = ioc_list.IOCList("uuid").list_datasets()
    pool = ioc_json.IOCJson().json_get_value("pool")
    date = datetime.datetime.utcnow().strftime("%F_%T")

    _jail = {uuid: path for (uuid, path) in jails.items() if
             uuid.startswith(jail)}

    if len(_jail) == 1:
        uuid, path = next(iter(_jail.items()))
    elif len(_jail) > 1:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for u, p in sorted(_jail.items()):
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"  {u} ({p})"
            })
        exit(1)
    else:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": f"{jail} not found!"
        }, exit_on_error=True)

    # If they don't supply a snapshot name, we will use the date.
    if not name:
        name = date

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    conf = ioc_json.IOCJson(path).json_load()

    if conf["template"] == "yes":
        target = f"{pool}/iocage/templates/{uuid}@{name}"
    else:
        target = f"{pool}/iocage/jails/{uuid}@{name}"

    try:
        su.check_call(["zfs", "snapshot", "-r", target], stderr=su.PIPE)
        ioc_common.logit({
            "level"  : "INFO",
            "message": f"Snapshot: {target} created."
        })
    except su.CalledProcessError:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Snapshot already exists!"
        }, exit_on_error=True)
