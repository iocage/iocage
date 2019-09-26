# Copyright (c) 2014-2019, iocage
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
import iocage_lib.ioc_common as ioc_common
import iocage_lib.iocage as ioc

from iocage_lib.dataset import Dataset

__rootcmd__ = True


def child_test(iocroot, name, _type, force=False, recursive=False):
    """Tests for dependent children"""
    path = None
    children = []
    paths = [f"{iocroot}/jails/{name}/root",
             f"{iocroot}/releases/{name}",
             f"{iocroot}/templates/{name}/root"]

    for p in paths:
        if os.path.isdir(p):
            path = p
            children = Dataset(path).snapshots_recursive()

            break

    if path is None:
        if not force:
            ioc_common.logit({
                "level": "WARNING",
                "message": "Partial UUID/NAME supplied, cannot check for "
                           "dependant jails."
            })

            if not click.confirm("\nProceed?"):
                exit()
        else:
            return

    _children = []

    for child in children:
        _name = child.name
        _children.append(f"  {_name}\n")

    sort = ioc_common.ioc_sort("", "name", data=_children)
    _children.sort(key=sort)

    if len(_children) != 0:
        if not force and not recursive:
            ioc_common.logit({
                "level": "WARNING",
                "message": f"\n{name} has dependent jails"
                           " (who may also have dependents),"
                           " use --recursive to destroy: "
            })

            ioc_common.logit({
                "level": "WARNING",
                "message": "".join(_children)
            })
            exit(1)
        else:
            return _children


@click.command(name="destroy", help="Destroy specified jail(s).")
@click.option("--force", "-f", default=False, is_flag=True,
              help="Destroy the jail without warnings or more user input.")
@click.option("--release", "-r", default=False, is_flag=True,
              help="Destroy a specified RELEASE dataset.")
@click.option("--recursive", "-R", default=False, is_flag=True,
              help="Bypass the children prompt, best used with --force (-f).")
@click.option("--download", "-d", default=False, is_flag=True,
              help="Destroy the download dataset of the specified RELEASE as"
                   " well.")
@click.argument("jails", nargs=-1)
def cli(force, release, download, jails, recursive):
    """Destroys the jail's 2 datasets and the snapshot from the RELEASE."""
    # Want these here, otherwise they're reinstanced for each jail.
    iocroot = ioc.PoolAndDataset().get_iocroot()

    if download and not release:
        ioc_common.logit({
            "level": "EXCEPTION",
            "message": "--release (-r) must be specified as well!"
        })

    if jails and not release:
        for jail in jails:
            iocage = ioc.IOCage(jail=jail, skip_jails=True)
            # If supplied a partial, we want the real match we got.
            jail, _ = iocage.__check_jail_existence__()

            if not force:
                ioc_common.logit({
                    "level": "WARNING",
                    "message": f"\nThis will destroy jail {jail}"
                })

                if not click.confirm("\nAre you sure?"):
                    continue  # no, continue to next jail

            child_test(iocroot, jail, "jail", force=force,
                       recursive=recursive)

            iocage.destroy_jail(force=force)
    elif jails and release:
        for release in jails:
            if not force:
                ioc_common.logit({
                    "level": "WARNING",
                    "message": f"\nThis will destroy RELEASE: {release}"
                })

                if not click.confirm("\nAre you sure?"):
                    continue

            children = child_test(iocroot, release, "release",
                                  force=force, recursive=recursive)

            if children:
                for child in children:
                    ioc.IOCage(jail=child).destroy_jail(force)

            ioc.IOCage(jail=release,
                       skip_jails=True).destroy_release(download)
    elif not jails and release:
        ioc_common.logit({
            "level": "EXCEPTION",
            "message": "Please specify one or more RELEASEs!"
        })
    else:
        ioc_common.logit({
            "level": "EXCEPTION",
            "message": "Please specify one or more jails!"
        })
