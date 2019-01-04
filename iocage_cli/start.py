# Copyright (c) 2014-2019, iocage
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

import iocage_lib.ioc_common as ioc_common
import iocage_lib.iocage as ioc

__rootcmd__ = True


@click.command(name='start', help='Starts the specified jails or ALL.')
@click.option(
    '--rc', default=False, is_flag=True,
    help='Will start all jails with boot=on, in the specified order with '
         'smaller value for priority starting first.'
)
@click.option(
    '--ignore', '-i', default=False, is_flag=True,
    help='Suppress exceptions for jails which fail to start'
)
@click.argument("jails", nargs=-1)
def cli(rc, jails, ignore):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to start_jail.
    """
    if not jails and not rc:
        ioc_common.logit({
            'level': 'EXCEPTION',
            'message': 'Usage: iocage start [OPTIONS] JAILS...\n'
                       '\nError: Missing argument "jails".'
        })

    if rc:
        ioc.IOCage(rc=rc, silent=True).start(ignore_exception=ignore)
    else:
        for jail in jails:
            ioc.IOCage(jail=jail, rc=rc).start(ignore_exception=ignore)
