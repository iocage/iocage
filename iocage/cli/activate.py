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
"""activate module for the cli."""
import click
import libzfs

import iocage.lib.Datasets
import iocage.lib.Logger

__rootcmd__ = True


@click.command(name="activate", help="Set a zpool active for iocage usage.")
@click.argument("zpool")
@click.option("--log-level", "-d", default=None)
@click.option("--mountpoint", "-m", default="/iocage")
def cli(zpool, log_level, mountpoint):
    """Calls ZFS set to change the property org.freebsd.ioc:active to yes."""
    logger = lib.Logger.Logger(print_level=log_level)
    zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
    iocage_pool = None

    for pool in zfs.pools:
        if pool.name == zpool:
            iocage_pool = pool

    if iocage_pool is None:
        logger.error(f"ZFS pool '{zpool}' not found")
        exit(1)

    try:
        datasets = lib.Datasets.Datasets(pool=iocage_pool, zfs=zfs, logger=logger)
        datasets.activate(mountpoint=mountpoint)
        logger.log(f"ZFS pool '{zpool}' activated")
    except:
        raise
        exit(1)
