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
"""
Apply operating system updates to jails.

When a release was fetched, patches are downloaded. Standalone jails that
were forked from a release that received new updates needs to apply them.
No network connection is required, as the previously downloaded patches
are temporarily mounted and applied with securelevel=0.
"""
import click
import typing

import iocage.errors
import iocage.Jails
import iocage.Logger
import iocage.Config.Jail.File.Fstab

from .shared.click import IocageClickContext

__rootcmd__ = True


@click.command(name="start", help="Starts the specified jails or ALL.")
@click.pass_context
@click.argument("jails", nargs=-1)
def cli(
    ctx: IocageClickContext,
    jails: typing.Tuple[str, ...]
) -> typing.Optional[bool]:
    """Update jails with patches from their releases."""
    logger = ctx.parent.logger
    print_function = ctx.parent.print_events

    if len(jails) == 0:
        logger.error("No jail selector provided")
        exit(1)

    filters = jails + ("template=no,-", "basejail=no",)
    ioc_jails = iocage.Jails.JailsGenerator(
        logger=logger,
        host=ctx.parent.host,
        zfs=ctx.parent.zfs,
        filters=filters
    )

    changed_jails = []
    failed_jails = []
    for jail in ioc_jails:
        try:
            changed = print_function(jail.updater.apply())
            if changed is True:
                changed_jails.append(jail)
        except iocage.errors.UpdateFailure:
            failed_jails.append(jail)

    if len(failed_jails) > 0:
        return False

    if len(changed_jails) == 0:
        jails_input = " ".join(list(jails))
        logger.error(
            f"No non-basejail was updated or matched your input: {jails_input}"
        )
        return False

    return True
