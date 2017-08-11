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
"""fstab module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="fstab", help="Manipulate the specified jails fstab.")
@click.argument("jail")
@click.argument("fstab_string", nargs=-1)
@click.option("--add", "-a", "action",
              help="Adds an entry to the jails fstab and mounts it.",
              flag_value="add")
@click.option("--remove", "-r", "action",
              help="Removes an entry from the jails fstab and unmounts it.",
              flag_value="remove")
@click.option("--edit", "-e", "action",
              help="Opens up the fstab file in your environments EDITOR.",
              flag_value="edit")
@click.option("--list", "-l", "action",
              help="Lists the jails fstab.", flag_value="list")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
def cli(action, fstab_string, jail, header):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to manipulate the fstab.
    """
    index = None
    _index = False
    add_path = False
    fstab_string = list(fstab_string)

    if not fstab_string and action != "edit" and action != "list":
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please supply a fstab entry or jail!"
        }, exit_on_error=True)

    # The user will expect to supply a string, the API would prefer these
    # separate. If the user supplies a quoted string, we will split it,
    # otherwise the format is acceptable to be imported directly.
    if len(fstab_string) == 1:
        try:
            source, destination, fstype, options, dump, _pass = fstab_string[
                0].split()
        except ValueError:
            # We're going to assume this is an index number.
            try:
                index = int(fstab_string[0])

                _index = True
                source, destination, fstype, options, dump, _pass = "", "", \
                                                                    "", "", \
                                                                    "", ""
            except TypeError:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": "Please specify either a valid fstab "
                               "entry or an index number."
                }, exit_on_error=True)
            except ValueError:
                # We will assume this is just a source, and will do a readonly
                # nullfs mount
                source = fstab_string[0]
                destination = source
                fstype = "nullfs"
                options = "ro"
                dump = "0"
                _pass = "0"
    elif action == "list":
        # We don't need these
        source, destination, fstype, options, dump, _pass = "", "", \
                                                            "", "", \
                                                            "", ""
    else:
        if action != "edit":
            try:
                source, destination, fstype, options, dump, _pass = \
                    fstab_string
            except ValueError:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": "Please specify a valid fstab entry!\n\n"
                               "Example:\n  /the/source /dest FSTYPE "
                               "FSOPTIONS FSDUMP FSPASS"
                }, exit_on_error=True)
        else:
            source, destination, fstype, options, dump, _pass = "", "", \
                                                                "", "", \
                                                                "", ""

    if not _index:
        add_path = True

    fstab = ioc.IOCage(exit_on_error=True, jail=jail).fstab(
        action, source, destination, fstype, options, dump, _pass, index=index,
        add_path=add_path, header=header)

    if action == "list":
        if header:
            ioc_common.logit({
                "level"  : "INFO",
                "message": fstab
            })
        else:
            for f in fstab:
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"{f[0]}\t{f[1]}"
                })
