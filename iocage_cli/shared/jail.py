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
"""Get a specific jails with this CLI helper function."""
import typing

import iocage.errors
import iocage.Jail
import iocage.Logger

from .click import IocageClickContext


def get_jail(
    jail_name: str,
    ctx: IocageClickContext
) -> iocage.Jail.JailGenerator:
    """Return the jail matching the given name."""
    try:
        return iocage.Jail.JailGenerator(
            jail_name,
            logger=ctx.logger,
            host=ctx.host
        )
    except iocage.errors.IocageException:
        exit(1)


def set_properties(
    properties: typing.Iterable[str],
    target: 'iocage.LaunchableResource.LaunchableResource'
) -> set:
    """Set a bunch of jail properties from a Click option tuple."""
    updated_properties = set()

    for prop in properties:

        if _is_setter_property(prop):
            key, value = prop.split("=", maxsplit=1)
            changed = target.config.set(key, value)
            if changed:
                updated_properties.add(key)
        else:
            key = prop
            try:
                del target.config[key]
                updated_properties.add(key)
            except (iocage.errors.IocageException, KeyError):
                pass

    if len(updated_properties) > 0:
        target.save()

    return updated_properties


def _is_setter_property(property_string: str) -> bool:
    return ("=" in property_string)
