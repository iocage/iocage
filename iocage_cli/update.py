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
"""update module for the cli."""
import click
import iocage_lib.iocage as ioc

__rootcmd__ = True


@click.command(
    name='update',
    help='Run freebsd-update to update a specified '
    'jail to the latest patch level.'
)
@click.option(
    '--pkgs', '-P', default=False, is_flag=True,
    help='Decide whether or not to update the pkg repositories and '
         'all installed packages in jail( this has no effect for plugins ).'
)
@click.option(
    "--server", "-s", default="download.freebsd.org",
    help="Server to fetch from."
)
@click.argument('jail', required=True)
def cli(jail, **kwargs):
    """Update the supplied jail to the latest patchset"""
    skip_jails = bool(jail != 'ALL')
    ioc.IOCage(jail=jail, skip_jails=skip_jails).update(**kwargs)
