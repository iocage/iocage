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
"""Activate zfs pools for iocage with the CLI."""
import click

import iocage.errors
import iocage.Datasets
import iocage.Logger
import iocage.ZFS

__rootcmd__ = True


@click.command(name="activate", help="Set a zpool active for iocage usage.")
@click.pass_context
@click.argument("zpool")
@click.option("--mountpoint", "-m", default="/iocage")
def cli(ctx, zpool, mountpoint):
    """Call ZFS set to change the property org.freebsd.ioc:active to yes."""
    logger = ctx.parent.logger
    zfs = ctx.parent.zfs

    if ctx.parent.user_sources is not None:
        logger.error("Cannot activate when executed with explicit sources.")
        exit(1)

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
        datasets.activate_pool(
            pool=iocage_pool,
            mountpoint=mountpoint
        )
        logger.log(f"ZFS pool '{zpool}' activated")
    except iocage.errors.IocageException:
        exit(1)
