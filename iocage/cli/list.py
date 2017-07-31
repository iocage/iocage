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
"""list module for the cli."""
import click
import texttable

import Jails
import Host
import Logger


@click.command(name="list", help="List a specified dataset type, by default"
                                 " lists all jails.")
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
@click.option("--log-level", "-d", default="info")
@click.option("--output", "-o", default=None)
def cli(dataset_type, header, _long, remote, plugins,
        _sort, quick, log_level, output):

    logger = Logger.Logger(print_level=log_level)
    host = Host.Host(logger=logger)
    jails = Jails.Jails(logger=logger)
    hardened = host.distribution.name == "HardenedBSD"

    if dataset_type is None:
        dataset_type = "all"

    if remote and not plugins:

        available_releases = host.distribution.releases
        for available_release in available_releases:
            print(available_release.name)
        return

    if plugins and remote:
        raise Exception("ToDo")
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

        table_data = []
        table_data.append([x.upper() for x in columns])

        for jail in jails.list():
            table_data.append([
                str(jail.getattr_str(x)) if x in [
                    "jid",
                    "name",
                    "running",
                    "ip4.addr",
                    "ip6.addr"
                ] else str(jail.config.__getattr__(x)
                           ) for x in columns])

        table.add_rows(table_data)
        print(table.draw())
        return

    return
