# Copyright (c) 2014-2018, iocage
# Copyright (c) 2017-2018, Stefan Grönke
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
"""Deactivate ZFS pools for iocage with the CLI."""
import click

import iocage.errors
import iocage.Datasets
import iocage.Logger
import iocage.ZFS

__rootcmd__ = True


@click.command(name="deactivate", help="Disable a ZFS pool for iocage.")
@click.pass_context
@click.argument("zpool")
def cli(ctx, zpool):
    """Call ZFS set to change the property org.freebsd.ioc:active to no."""
    logger = ctx.parent.logger
    zfs = ctx.parent.zfs

    try:
        iocage_pool = zfs.get(zpool)
    except Exception:
        logger.error(f"ZFS pool '{zpool}' not found")
        exit(1)

    try:
        datasets = iocage.Datasets.Datasets(
            zfs=zfs,
            logger=logger
        )
        datasets.attach_source("iocage", f"{iocage_pool.name}/iocage")
        if datasets.is_pool_active():
            datasets.deactivate()
            logger.log(f"ZFS pool '{zpool}' deactivated")
        else:
            logger.warn(f"ZFS pool '{zpool}' is not active")
    except iocage.errors.IocageException:
        exit(1)
