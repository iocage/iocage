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
"""clone module for the cli."""
import click

import iocage_lib.ioc_common as ioc_common
import iocage_lib.iocage as ioc

__rootcmd__ = True


def validate_count(ctx, param, value):
    """Takes a string, removes the commas and returns an int."""
    if isinstance(value, str):
        try:
            value = value.replace(',', '')

            return int(value)
        except ValueError:
            ioc_common.logit({
                'level': 'EXCEPTION',
                'message': f'({value} is not a valid  integer.'
            })
    else:
        return int(value)


@click.command(name='clone', help='Clone a jail.')
@click.argument('source', nargs=1)
@click.argument('props', nargs=-1)
@click.option('--count', '-c', callback=validate_count, default='1')
@click.option('--name', '-n', default=None,
              help='Provide a specific name instead of an UUID for this jail')
@click.option('--newmac', '-N', is_flag=True, default=False,
              help='Regenerate the clones MAC address')
@click.option('--uuid', '-u', '_uuid', default=None,
              help='Provide a specific UUID for this jail')
@click.option('--thickjail', '-T', is_flag=True, default=False,
              help='Set the new jail type to a thickjail. Thickjails'
                   ' are copied (not cloned) from the specified target.')
def cli(source, props, count, name, _uuid, thickjail, newmac):
    # At this point we don't care
    _uuid = name if name else _uuid
    props = list(props)

    if newmac:
        for p in ('vnet0', 'vnet1', 'vnet2', 'vnet3'):
            props.append(f'{p}_mac=none')

    ioc.IOCage(jail=source, skip_jails=True).create(
        source, props, count, _uuid=_uuid, thickjail=thickjail, clone=True
    )
