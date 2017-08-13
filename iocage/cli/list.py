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
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANYw
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""list module for the cli."""
import click
import texttable

import iocage.lib.Jails
import iocage.lib.Host
import iocage.lib.Logger


@click.command(name="list", help="List a specified dataset type, by default"
                                 " lists all jails.")
@click.pass_context
@click.option("--release", "--base", "-r", "-b", "dataset_type",
              flag_value="base", help="List all bases.")
@click.option("--template", "-t", "dataset_type", flag_value="template",
              help="List all templates.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full uuid and ip4 address.")
@click.option("--remote", "-R", is_flag=True, help="Show remote's available "
                                                   "RELEASEs.")
@click.option("--plugins", "-P", is_flag=True, help="Show available plugins.")
@click.option("--sort", "-s", "_sort", default="name", nargs=1,
              help="Sorts the list by the given type")
@click.option("--quick", "-q", is_flag=True, default=False,
              help="Lists all jails with less processing and fields.")
@click.option("--log-level", "-d", default=None)
@click.option("--output", "-o", default=None)
@click.argument("filters", nargs=-1)
def cli(ctx, dataset_type, header, _long, remote, plugins,
        _sort, quick, log_level, output, filters):

    logger = ctx.parent.logger
    logger.print_level = log_level

    host = iocage.lib.Host.Host(logger=logger)
    jails = iocage.lib.Jails.Jails(logger=logger)

    if dataset_type is None:
        dataset_type = "all"

    if remote and not plugins:

        available_releases = host.distribution.releases
        for available_release in available_releases:
            print(available_release.name)
        return

    if plugins and remote:
        raise Exception("ToDo: Plugins")
    else:

        if output:
            columns = output.strip().split(',')
        else:
            columns = ["jid", "name"]

            if _long:
                columns += ["uuid", "running",
                            "release", "ip4.addr", "ip6.addr"]
            else:
                columns += ["running", "ip4.addr"]

        table = texttable.Texttable(max_width=0)
        table.set_cols_dtype(["t"] * len(columns))

        table_head = (list(x.upper() for x in columns))
        table_data = []

        try:
            sort_index = columns.index(_sort)
        except ValueError:
            sort_index = None

        for jail in jails.list(filters=filters):
            table_data.append(
                [_lookup_jail_value(jail, x) for x in columns]
            )

        if sort_index is not None:
            table_data.sort(key=lambda x: x[sort_index])

        table.add_rows([table_head] + table_data)
        print(table.draw())

    return


def _lookup_jail_value(jail, key):
    if key in iocage.lib.Jails.Jails.JAIL_KEYS:
        return jail.getattr_str(key)
    else:
        return str(jail.config.__getitem__(key))
