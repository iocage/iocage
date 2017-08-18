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
"""start module for the cli."""
import click

import iocage.lib.Jails
import iocage.lib.Logger


__rootcmd__ = True


@click.command(name="start", help="Starts the specified jails or ALL.")
@click.pass_context
@click.option("--rc", default=False, is_flag=True,
              help="Will start all jails with boot=on, in the specified"
                   " order with smaller value for priority starting first.")
@click.option("--log-level", "-d", default=None)
@click.argument("jails", nargs=-1)
def cli(ctx, rc, jails, log_level):
    """
    Starts Jails
    """

    logger = ctx.parent.logger
    logger.print_level = log_level
    ioc_jails = iocage.lib.Jails.Jails(logger=logger)

    for jail in ioc_jails.list(filters=jails):
        logger.log(f"Starting {jail.humanreadable_name}")
        try:
            jail.start()
        except Exception:
            raise
            exit(1)

        logger.log(f"{jail.humanreadable_name} running as JID {jail.jid}")
        exit(0)
