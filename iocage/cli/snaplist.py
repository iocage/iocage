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
"""snaplist module for the cli."""
import subprocess as su

import click
import texttable

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list


@click.command(name="snaplist", help="Show snapshots of a specified jail.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.argument("jail")
def cli(header, jail):
    """Allows a user to show resource usage of all jails."""
    jails, paths = ioc_list.IOCList("uuid").list_datasets()
    pool = ioc_json.IOCJson().json_get_value("pool")
    snap_list = []
    table = texttable.Texttable(max_width=0)

    _jail = {tag: uuid for (tag, uuid) in jails.items() if
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

    conf = ioc_json.IOCJson(path).json_load()

    if conf["template"] == "yes":
        full_path = f"{pool}/iocage/templates/{tag}"
    else:
        full_path = f"{pool}/iocage/jails/{uuid}"

    zconf = ["zfs", "get", "-H", "-o", "value"]
    snapshots = su.Popen(["zfs", "list", "-r", "-H", "-t", "snapshot",
                          full_path], stdout=su.PIPE,
                         stderr=su.PIPE).communicate()[0].decode(
        "utf-8").split("\n")

    for snap in snapshots:
        # We get an empty list at the end.
        if snap:
            snap = snap.split()
            snapname = snap[0].rsplit("@")[1]
            root_snapname = snap[0].rsplit("@")[0].split("/")[-1]

            if root_snapname == "root":
                snapname += "/root"
            elif root_snapname != uuid and root_snapname != tag:
                # basejail datasets.
                continue

            creation = su.Popen(zconf + ["creation", snap[0]],
                                stdout=su.PIPE).communicate()[0].decode(
                "utf-8").strip()
            used = snap[1]
            referenced = su.Popen(zconf + ["referenced", snap[0]],
                                  stdout=su.PIPE).communicate()[0].decode(
                "utf-8").strip()

            snap_list.append([snapname, creation, referenced, used])

    if header:
        snap_list.insert(0, ["NAME", "CREATED", "RSIZE", "USED"])
        # We get an infinite float otherwise.
        table.set_cols_dtype(["t", "t", "t", "t"])
        table.add_rows(snap_list)
        ioc_common.logit({
            "level"  : "INFO",
            "message": table.draw()
        })
    else:
        for snap in snap_list:
            ioc_common.logit({
                "level"  : "INFO",
                "message": "\t".join(snap)
            })
