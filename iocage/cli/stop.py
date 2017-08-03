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
"""stop module for the cli."""
import click

import Jail
import Logger

logger = Logger.Logger(print_level=False)

__rootcmd__ = True


@click.command(name="stop", help="Stops the specified jails or ALL.")
@click.option("--rc", default=False, is_flag=True,
              help="Will stop all jails with boot=on, in the specified"
                   " order with higher value for priority stopping first.")
@click.argument("jails", nargs=-1)
@click.option("--log-level", "-d", default=None)
def cli(rc, jails, log_level):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to stop_jail.
    """

    logger.print_level = log_level

    for jail_identifier in jails:
        jail = Jail.Jail(jail_identifier, logger=logger)
        logger.log(f"Stopping jail {jail.humanreadable_name}")
        try:
            jail.stop()
        except Exception as e:
            exit(1)

        logger.log("done")
        exit(0)
