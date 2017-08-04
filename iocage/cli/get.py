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
"""get module for the cli."""
import click
import texttable

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc


@click.command(context_settings=dict(
    max_content_width=400, ), name="get", help="Gets the specified property.")
@click.argument("prop", required=True, default="")
@click.argument("jail", required=True, default="")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--recursive", "-r", help="Get the specified property for all " +
                                        "jails.", flag_value="recursive")
@click.option("--plugin", "-P",
              help="Get the specified key for a plugin jail, if accessing a"
                   " nested key use . as a separator."
                   "\n\b Example: iocage get -P foo.bar.baz PLUGIN",
              is_flag=True)
@click.option("--all", "-a", "_all", help="Get all properties for the "
                                          "specified jail.", is_flag=True)
@click.option("--pool", "-p", "_pool", help="Get the currently activated "
                                            "zpool.", is_flag=True)
def cli(prop, _all, _pool, jail, recursive, header, plugin):
    """Get a list of jails and print the property."""
    table = texttable.Texttable(max_width=0)

    if _all:
        # Confusing I know.
        jail = prop
        prop = "all"
    elif _pool:
        pool = ioc.IOCage(skip_jails=True).get("", pool=True)
        ioc_common.logit({
            "level"  : "INFO",
            "message": pool
        })
        exit()
    else:
        if not jail and not recursive:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": "You must specify a jail!"
            })

    if _all and recursive:
        # TODO: Port this back
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "You cannot use --all (-a) and --recursive (-r) "
                       "together. "
        })

    if not recursive:
        if prop == "state":
            state = ioc.IOCage(jail).get(prop)

            ioc_common.logit({
                "level"  : "INFO",
                "message": state
            })
        elif plugin:
            _plugin = ioc.IOCage(jail, skip_jails=True).get(prop, plugin=True)

            ioc_common.logit({
                "level"  : "INFO",
                "message": _plugin
            })
        elif prop == "all":
            props = ioc.IOCage(jail, skip_jails=True).get(prop)

            for p, v in props.items():
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"{p}:{v}"
                })
        else:
            p = ioc.IOCage(jail, skip_jails=True).get(prop)

            ioc_common.logit({
                "level"  : "INFO",
                "message": p
            })
    else:
        jails = ioc.IOCage().get(prop, recursive=True)
        table.header(["NAME", f"PROP - {prop}"])

        for jail_dict in jails:
            for jail, prop in jail_dict.items():
                if header:
                    table.add_row([jail, prop])
                else:
                    ioc_common.logit({
                        "level"  : "INFO",
                        "message": f"{jail}\t{prop}"
                    })

        if header:
            # Prints the table
            ioc_common.logit({
                "level"  : "INFO",
                "message": table.draw()
            })
