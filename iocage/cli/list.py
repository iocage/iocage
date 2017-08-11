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

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_fetch as ioc_fetch
import iocage.lib.iocage as ioc


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
@click.option("--http", default=False,
              help="Have --remote use HTTP instead.", is_flag=True)
@click.option("--sort", "-s", "_sort", default="name", nargs=1,
              help="Sorts the list by the given type")
@click.option("--quick", "-q", is_flag=True, default=False,
              help="Lists all jails with less processing and fields.")
def cli(dataset_type, header, _long, remote, http, plugins, _sort, quick):
    """This passes the arg and calls the jail_datasets function."""
    freebsd_version = ioc_common.checkoutput(["freebsd-version"])
    iocage = ioc.IOCage(exit_on_error=True, skip_jails=True)

    if dataset_type is None:
        dataset_type = "all"

    if remote and not plugins:
        if "HBSD" in freebsd_version:
            hardened = True
        else:
            hardened = False

        ioc_fetch.IOCFetch("", http=http, hardened=hardened).fetch_release(
            _list=True)

    if plugins and remote:
        _list = ioc_fetch.IOCFetch("").fetch_plugin_index("", _list=True,
                                                          list_header=header,
                                                          list_long=_long)
    else:
        _list = iocage.list(dataset_type, header, _long, _sort,
                            plugin=plugins, quick=quick)

    if not header:
        if dataset_type == "base":
            for item in _list:
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": item
                })
        else:
            for item in _list:
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": "\t".join(item)
                })
    else:
        ioc_common.logit({
            "level"  : "INFO",
            "message": _list
        })
