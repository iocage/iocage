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

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(context_settings=dict(
    ignore_unknown_options=True, ),
    name="exec", help="Run a command inside a specified jail.")
@click.option("--host_user", "-u", default="root",
              help="The host user to use.")
@click.option("--jail_user", "-U", help="The jail user to use.")
@click.argument("jail", required=True, nargs=1)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def cli(command, jail, host_user, jail_user):
    """Runs the command given inside the specified jail as the supplied
    user."""
    # We may be getting ';', '&&' and so forth. Adding the shell for safety.
    if len(command) == 1:
        command = ("/bin/sh", "-c") + command

    if jail.startswith("-"):
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify a jail first!"
        }, exit_on_error=True)

    # They haven't set a host_user then, and actually want a jail one,
    # unsetting the convenience default
    host_user = "" if jail_user and host_user == "root" else host_user

    ioc.IOCage(exit_on_error=True, jail=jail).exec(command, host_user,
                                                   jail_user)
