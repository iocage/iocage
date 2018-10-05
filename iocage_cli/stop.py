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
"""Stop jails with the CLI."""
import typing
import click

import iocage.errors
import iocage.Jails
import iocage.Logger

from .shared.click import IocageClickContext

__rootcmd__ = True


@click.command(name="stop", help="Stops the specified jails or ALL.")
@click.pass_context
@click.option("--rc", default=False, is_flag=True,
              help="Will stop all jails with boot=on, in the specified"
                   " order with higher value for priority stopping first.")
@click.option("--force", "-f", is_flag=True, default=False,
              help="Skip checks and enforce jail shutdown")
@click.argument("jails", nargs=-1)
def cli(
    ctx: IocageClickContext,
    rc: bool,
    force: bool,
    jails: typing.Tuple[str, ...]
) -> None:
    """
    Stop a jail.

    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail.
    """
    logger = ctx.parent.logger
    stop_args = {
        "logger": logger,
        "zfs": ctx.parent.zfs,
        "host": ctx.parent.host,
        "print_function": ctx.parent.print_events,
        "force": force
    }

    if (rc is False) and (len(jails) == 0):
        logger.error("No jail selector provided")
        exit(1)

    elif rc is True:
        if len(jails) > 0:
            logger.error("Cannot use --rc and jail selectors simultaniously")
            exit(1)

        _autostop(
            host=ctx.parent.host,
            zfs=ctx.parent.zfs,
            logger=logger,
            print_function=ctx.parent.print_events,
            force=force
        )
    else:
        if not _normal(jails, **stop_args):
            exit(1)


def _normal(
    filters: typing.Tuple[str, ...],
    zfs: iocage.Host.HostGenerator,
    host: iocage.Host.HostGenerator,
    logger: iocage.Logger.Logger,
    print_function: typing.Callable[
        [typing.Generator[iocage.events.IocageEvent, None, None]],
        None
    ],
    force: bool
) -> bool:

    filters += ("template=no,-",)

    jails = iocage.Jails.JailsGenerator(
        zfs=zfs,
        host=host,
        logger=logger,
        filters=filters
    )

    changed_jails = []
    failed_jails = []
    for jail in jails:
        try:
            print_function(jail.stop(force=force))
        except iocage.errors.IocageException:
            failed_jails.append(jail)
            continue

        logger.log(f"{jail.name} stopped")
        changed_jails.append(jail)

    if len(failed_jails) > 0:
        return False

    if len(changed_jails) == 0:
        jails_input = " ".join(list(jails))
        logger.error(f"No jails matched your input: {jails_input}")
        return False

    return True


def _autostop(
    zfs: iocage.ZFS.ZFS,
    host: iocage.Host.HostGenerator,
    logger: iocage.Logger.Logger,
    print_function: typing.Callable[
        [typing.Generator[iocage.events.IocageEvent, None, None]],
        None
    ],
    force: bool=True
) -> None:

    filters = ("running=yes", "template=no,-",)

    ioc_jails = iocage.Jails.Jails(
        host=host,
        zfs=zfs,
        logger=logger,
        filters=filters
    )

    # sort jails by their priority
    jails = reversed(sorted(
        list(ioc_jails),
        key=lambda x: x.config["priority"]
    ))

    failed_jails = []
    for jail in jails:
        try:
            jail.stop(force=force)
        except iocage.errors.IocageException:
            failed_jails.append(jail)
            continue

        logger.log(f"{jail.name} stopped")

    if len(failed_jails) > 0:
        exit(1)
