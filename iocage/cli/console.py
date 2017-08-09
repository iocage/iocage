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
"""console module for the cli."""

import click

import iocage.lib.Jail
import iocage.lib.Logger

__rootcmd__ = True


@click.command(name="console", help="Login to a jail.")
@click.argument("jail")
@click.option("--log-level", "-d", default=None)
def cli(jail, log_level):
    """
    Runs jexec to login into the specified jail.
    """
    logger = lib.Logger.Logger(print_level=False)
    logger.print_level = log_level

    jail = lib.Jail.Jail(jail, logger=logger)
    jail.update_jail_state()

    if not jail.exists:
        logger.error(f"The jail {jail.humanreadable_name} does not exist")
        exit(1)
    if not jail.running:
        logger.error(f"The jail {jail.humanreadable_name} is not running")
        exit(1)
    else:
        jail.exec_console()
