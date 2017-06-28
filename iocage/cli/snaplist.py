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
import click
import texttable

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc


@click.command(name="snaplist", help="Show snapshots of a specified jail.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full dataset path for snapshot name.")
@click.argument("jail")
def cli(header, jail, _long):
    """Allows a user to show resource usage of all jails."""
    table = texttable.Texttable(max_width=0)
    snap_list = ioc.IOCage(jail).snap_list(_long)

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
