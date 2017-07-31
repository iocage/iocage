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
"""set module for the cli."""
import click

import Jail

__rootcmd__ = True


@click.command(context_settings=dict(
    max_content_width=400, ), name="set", help="Sets the specified property.")
@click.argument("props", nargs=-1)
@click.argument("jail", nargs=1)
# @click.option("--plugin", "-P",
#               help="Set the specified key for a plugin jail, if accessing a"
#                    " nested key use . as a separator."
#                    "\n\b Example: iocage set -P foo.bar.baz=VALUE PLUGIN",
#               is_flag=True)
# def cli(props, jail, plugin):
def cli(props, jail):
    """Get a list of jails and print the property."""
    print(jail, props)
    jail = Jail.Jail(jail)
    for prop in props:

        delete = False

        try:
            key, value = prop.split("=", maxsplit=1)
        except:
            delete = True

        if delete:
            del jail.config[key]
        else:
            jail.config.__setattr__(key, value)

    jail.config.save()
