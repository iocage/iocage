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
"""Get a configuration value from the CLI."""
import typing
import click

import iocage.errors
import iocage.Host
import iocage.Jail
import iocage.Logger

from .shared.click import IocageClickContext


@click.command(
    context_settings=dict(max_content_width=400,),
    name="get",
    help="Gets the specified property."
)
@click.pass_context
@click.argument("prop", nargs=-1, required=False, default=None)
@click.argument("jail", nargs=1, required=True)
@click.option(
    "--all", "-a", "_all",
    help="Get all properties for the specified jail.",
    is_flag=True
)
def cli(
    ctx: IocageClickContext,
    prop: typing.Tuple[str],
    _all: bool,
    jail: typing.Optional[str]
) -> None:
    """Get a list of jails and print the property."""
    logger = ctx.parent.logger
    host = iocage.Host.Host(logger=logger)

    _prop = None if len(prop) == 0 else prop[0]

    if _all is True:
        if jail is None:
            jail = _prop
        _prop = None

    if _prop == "all":
        _prop = None

    if jail == "defaults":
        source_resource = host.defaults
        source_resource.read_config()
        lookup_method = _lookup_config_value
    else:
        lookup_method = _lookup_jail_value
        try:
            source_resource = iocage.Jail.Jail(
                jail,
                host=host,
                logger=logger
            )
        except iocage.errors.JailNotFound as e:
            exit(1)

    if (_prop is None) and (jail == "") and not _all:
        logger.error("Missing arguments property and jail")
        exit(1)
    elif (_prop is not None) and (jail == ""):
        logger.error("Missing argument property name or -a/--all argument")
        exit(1)

    if _prop:
        value = lookup_method(source_resource, _prop)

        if value:
            print(value)
            return
        else:
            logger.error(f"Unknown property '{_prop}'")
            exit(1)

    for key in source_resource.config.all_properties:
        if (_prop is None) or (key == _prop):
            value = source_resource.config.get_string(key)
            _print_property(key, value)


def _print_property(key: str, value: str) -> None:
    print(f"{key}:{value}")


def _lookup_config_value(
    resource: 'iocage.Resource.Resource',
    key: str
) -> str:
    return str(iocage.helpers.to_string(resource.config[key]))


def _lookup_jail_value(
    resource: 'iocage.LaunchableResource.LaunchableResource',
    key: str
) -> str:

    if key == "running":
        value = resource.running
    else:
        value = resource.getstring(key)

    return str(iocage.helpers.to_string(value))
