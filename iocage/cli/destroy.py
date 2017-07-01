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
"""destroy module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="destroy", help="Destroy specified jail(s).")
@click.option("--force", "-f", default=False, is_flag=True,
              help="Destroy the jail without warnings or more user input.")
@click.option("--release", "-r", default=False, is_flag=True,
              help="Destroy a specified RELEASE dataset.")
@click.option("--download", "-d", default=False, is_flag=True,
              help="Destroy the download dataset of the specified RELEASE as"
                   " well.")
@click.argument("jails", nargs=-1)
def cli(force, release, download, jails):
    """Destroys the jail's 2 datasets and the snapshot from the RELEASE."""

    if download and not release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "--release (-r) must be specified as well!"
        })

    if jails and not release:
        for jail in jails:
            if not force:
                ioc_common.logit({
                    "level"  : "WARNING",
                    "message": f"\nThis will destroy jail {jail}"
                })

                if not click.confirm("\nAre you sure?"):
                    continue  # no, continue to next jail

            ioc.IOCage(jail, skip_jails=True).destroy_jail()
    elif jails and release:
        for release in jails:
            if not force:
                ioc_common.logit({
                    "level"  : "WARNING",
                    "message": f"\nThis will destroy RELEASE: {release} and "
                               "any jail that was created with it."
                })

                if not click.confirm("\nAre you sure?"):
                    continue

            ioc.IOCage(release, skip_jails=True).destroy_release(download)
    elif not jails and release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify one or more RELEASEs!"
        })
    else:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify one or more jails!"
        })
