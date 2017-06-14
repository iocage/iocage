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

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list

__rootcmd__ = True


@click.command(context_settings=dict(
    max_content_width=400, ), name="set", help="Sets the specified property.")
@click.argument("prop", nargs=-1)
@click.argument("jail")
@click.option("--plugin", "-P",
              help="Set the specified key for a plugin jail, if accessing a"
                   " nested key use . as a separator."
                   "\n\b Example: iocage set -P foo.bar.baz=VALUE PLUGIN",
              is_flag=True)
def cli(prop, jail, plugin):
    """Get a list of jails and print the property."""
    prop = " ".join(prop)  # We don't want a tuple.

    if "template" in prop:
        jail = f"{jail} (template)"

    if jail == "default":
        default = True
    else:
        default = False

    if not default:
        jails, paths = ioc_list.IOCList("uuid").list_datasets(set=True)
        _jail = {tag: uuid for (tag, uuid) in jails.items() if
                 uuid.startswith(jail) or tag == jail}

        if len(_jail) == 1:
            tag, uuid = next(iter(_jail.items()))
            path = paths[tag]
            iocjson = ioc_json.IOCJson(path, cli=True)
        elif len(_jail) > 1:
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"Multiple jails found for {jail}:"
            })
            for t, u in sorted(_jail.items()):
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"  {u} ({t})"
                })
            exit(1)
        else:
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"{jail} not found!"
            })
            exit(1)

        if "template" in prop.split("=")[0]:
            if "template" in path and prop != "template=no":
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"{uuid} ({tag}) is already a template!"
                })
                exit(1)
            elif "template" not in path and prop != "template=yes":
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"{uuid} ({tag}) is already a jail!"
                })
                exit(1)

        if plugin:
            _prop = prop.split(".")
            err = ioc_json.IOCJson(path, cli=True).json_plugin_set_value(_prop)
            if err:
                exit(1)
        else:
            try:
                # We use this to test if it's a valid property at all.
                _prop = prop.partition("=")[0]
                iocjson.json_get_value(_prop)

                # The actual setting of the property.
                iocjson.json_set_value(prop)
            except KeyError:
                _prop = prop.partition("=")[0]
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"{_prop} is not a valid property!"
                })
                exit(1)
    else:
        _, iocroot = ioc_json._get_pool_and_iocroot()
        ioc_json.IOCJson(iocroot).json_set_value(prop, default=True)
