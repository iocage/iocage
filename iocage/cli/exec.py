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
"""exec module for the cli."""
import click

import Jail
import Logger

logger = Logger.Logger(print_level=False)

__rootcmd__ = True


@click.command(context_settings=dict(ignore_unknown_options=True),
    name="exec", help="Run a command inside a specified jail.")
@click.option("--host_user", "-u", default="root",
              help="The host user to use.")
@click.option("--jail_user", "-U", help="The jail user to use.")
@click.argument("jail", required=True, nargs=1)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
@click.option("--log-level", "-d", default=None)
def cli(command, jail, host_user, jail_user, log_level):
    """Runs the command given inside the specified jail as the supplied
    user."""
    logger.print_level = log_level

    if jail.startswith("-"):
        logger.error("Please specify a jail first!")
        exit(1)

    user_command = " ".join(list(command))

    if jail_user:
        command = ["/bin/su", "-m",
                   escape_shell_arg(jail_user), "-c", user_command]
    else:
        command = ["/bin/sh", "-c", user_command]

    jail = Jail.Jail(jail, logger=logger)
    jail.update_jail_state()

    if not jail.exists:
        logger.error(f"The jail {jail.humanreadable_name} does not exist")
        exit(1)
    if not jail.running:
        logger.error(f"The jail {jail.humanreadable_name} is not running")
        exit(1)
    else:
        jail.passthru(command)


def escape_shell_arg(text):
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    return f"'{text}'"
