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
"""rollback module for the cli."""
import subprocess as su

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list

__rootcmd__ = True


@click.command(name="rollback", help="Rollbacks the specified jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=True)
@click.option("--force", "-f", help="Skip then interactive question.",
              default=False, is_flag=True)
def cli(jail, name, force):
    """Get a list of jails and print the property."""
    jails, paths = ioc_list.IOCList("uuid").list_datasets()
    pool = ioc_json.IOCJson().json_get_value("pool")

    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Multiple jails found for"
                       f" {jail}:"
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

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    conf = ioc_json.IOCJson(path).json_load()

    if conf["template"] == "yes":
        target = f"{pool}/iocage/templates/{tag}"
    else:
        target = f"{pool}/iocage/jails/{uuid}"

    try:
        ioc_common.checkoutput(["zfs", "get", "-H", "creation", target],
                               stderr=su.PIPE)
    except su.CalledProcessError:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"Snapshot {target} does not exist!"
        })
        exit(1)

    if not force:
        ioc_common.logit({
            "level"  : "WARNING",
            "message": "\nThis will destroy ALL data created since"
                       f" {name} was taken.\nIncluding ALL snapshots taken"
                       f" after {name} for {uuid} ({tag})"
        })
        if not click.confirm("\nAre you sure?"):
            exit()
    try:
        datasets = su.Popen(["zfs", "list", "-H", "-r",
                             "-o", "name", target],
                            stdout=su.PIPE,
                            stderr=su.PIPE).communicate()[0].decode(
            "utf-8").split()

        for dataset in datasets:
            su.check_call(
                ["zfs", "rollback", "-r", f"{dataset}@{name}"])

        ioc_common.logit({
            "level"  : "INFO",
            "message": f"Rolled back to: {target}"
        })
    except su.CalledProcessError as err:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{err}"
        })
        exit(1)
