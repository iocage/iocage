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
import os

import click
import libzfs

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


def child_test(zfs, iocroot, name, _type, force=False):
    """Tests for dependent children"""
    if _type == "jail":
        path = f"{iocroot}/jails/{name}/root"
    else:
        # RELEASE
        path = f"{iocroot}/releases/{name}"

    # While we would like to catch the zfs exception, it still prints to the
    #  display, this is the next best test.
    if os.path.isdir(path):
        children = zfs.get_dataset_by_path(path).snapshots_recursive
    else:
        if not force:
            ioc_common.logit({
                "level"  : "WARNING",
                "message": "Partial UUID/NAME supplied, cannot check for "
                           "dependant jails."
            })
            if not click.confirm("\nProceed?"):
                return
            children = []
        else:
            return

    _children = []

    for child in children:
        _name = child.name.rsplit("@", 1)[-1]
        if _type == "jail":
            path = path.replace(name, _name)
            if os.path.isdir(path):
                # We only want jails, not every snap they have.
                _children.append(f"  {_name}\n")
        else:
            _children.append(f"  {_name}\n")

    sort = ioc_common.ioc_sort("", "name", exit_on_error=True, data=_children)
    _children.sort(key=sort)

    if len(_children) != 0:
        if not force:
            ioc_common.logit({
                "level"  : "WARNING",
                "message": f"\n{name} has dependent jails,"
                           " use --force to destroy: "
            })

            ioc_common.logit({
                "level"  : "WARNING",
                "message": "".join(_children)
            })
            exit(1)
        else:
            return


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
    # Want these here, otherwise they're reinstanced for each jail.
    zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
    iocroot = ioc.PoolAndDataset().get_iocroot()

    if download and not release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "--release (-r) must be specified as well!"
        }, exit_on_error=True)

    if jails and not release:
        for jail in jails:
            if not force:
                ioc_common.logit({
                    "level"  : "WARNING",
                    "message": f"\nThis will destroy jail {jail}"
                })

                if not click.confirm("\nAre you sure?"):
                    continue  # no, continue to next jail

            child_test(zfs, iocroot, jail, "jail", force=force)

            ioc.IOCage(exit_on_error=True, jail=jail,
                       skip_jails=True).destroy_jail()
    elif jails and release:
        for release in jails:
            if not force:
                ioc_common.logit({
                    "level"  : "WARNING",
                    "message": f"\nThis will destroy RELEASE: {release}"
                })

                if not click.confirm("\nAre you sure?"):
                    continue

            child_test(zfs, iocroot, release, "release", force=force)

            ioc.IOCage(exit_on_error=True, jail=release,
                       skip_jails=True).destroy_release(download)
    elif not jails and release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify one or more RELEASEs!"
        }, exit_on_error=True)
    else:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify one or more jails!"
        }, exit_on_error=True)
