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
"""update module for the cli."""
import subprocess as su

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_fetch as ioc_fetch
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list
import iocage.lib.ioc_start as ioc_start
import iocage.lib.ioc_stop as ioc_stop

__rootcmd__ = True


@click.command(name="update", help="Run freebsd-update to update a specified "
                                   "jail to the latest patch level.")
@click.argument("jail", required=True)
def cli(jail):
    """Runs update with the command given inside the specified jail."""
    # TODO: Move to API
    jails = ioc_list.IOCList("uuid").list_datasets()
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
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
        exit(1)

    freebsd_version = ioc_common.checkoutput(["freebsd-version"])
    status, jid = ioc_list.IOCList.list_get_jid(uuid)
    conf = ioc_json.IOCJson(path).json_load()
    started = False

    if conf["type"] == "jail":
        if not status:
            ioc_start.IOCStart(uuid, path, conf, silent=True)
            status, jid = ioc_list.IOCList.list_get_jid(uuid)
            started = True
    elif conf["type"] == "basejail":
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please run \"iocage migrate\" before trying"
                       f" to update {uuid}"
        })
        exit(1)
    elif conf["type"] == "template":
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please convert back to a jail before trying"
                       f" to update {uuid}"
        })
        exit(1)
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{conf['type']} is not a supported jail type."
        })
        exit(1)

    if "HBSD" in freebsd_version:
        su.Popen(["hbsd-update", "-j", jid]).communicate()

        if started:
            ioc_stop.IOCStop(uuid, path, conf, silent=True)
    else:
        ioc_fetch.IOCFetch(conf["cloned_release"]).fetch_update(True, uuid)

        if started:
            ioc_stop.IOCStop(uuid, path, conf, silent=True)
