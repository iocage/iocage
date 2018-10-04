# Copyright (c) 2014-2018, iocage
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
"""List jails, releases and templates with the CLI."""
import click
import json
import typing

import iocage.errors
import iocage.Logger
import iocage.Host
import iocage.Resource
import iocage.ListableResource
import iocage.Jails
import iocage.Releases

from .shared.output import print_table
from .shared.click import IocageClickContext

__rootcmd__ = True

supported_output_formats = ['table', 'csv', 'list', 'json']


@click.command(
    name="list",
    help="List a specified dataset type, by default lists all jails."
)
@click.pass_context
@click.option("--release", "--base", "-r", "-b", "dataset_type",
              flag_value="base", help="List all bases.")
@click.option("--template", "-t", "dataset_type",
              flag_value="template", help="List all templates.")
@click.option("--dataset", "-d", "dataset_type",
              flag_value="datasets", help="List all root data sources.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full uuid and ip4 address.")
@click.option("--remote", "-R",
              is_flag=True, help="Show remote's available RELEASEs.")
@click.option("--sort", "-s", "_sort", default=None, nargs=1,
              help="Sorts the list by the given type")
@click.option("--output", "-o", default=None)
@click.option("--output-format", "-f", default="table",
              type=click.Choice(supported_output_formats))
@click.option("--header/--no-header", "-H/-NH", is_flag=True, default=True,
              help="Show or hide column name heading.")
@click.argument("filters", nargs=-1)
def cli(
    ctx: IocageClickContext,
    dataset_type: str,
    header: bool,
    _long: bool,
    remote: bool,
    _sort: typing.Optional[str],
    output: typing.Optional[str],
    output_format: str,
    filters: typing.Tuple[str, ...]
) -> None:
    """List jails in various formats."""
    logger = ctx.parent.logger
    host: iocage.Host.HostGenerator = ctx.parent.host

    if output is not None and _long is True:
        logger.error("--output and --long can't be used together")
        exit(1)

    if output_format != "table" and _sort is not None:
        # Sorting destroys the ability to stream generators
        # ToDo: Figure out if we need to sort other output formats as well
        raise Exception("Sorting only allowed for tables")

    # empty filters will match all jails
    if len(filters) == 0:
        filters += ("*",)

    columns: typing.List[str] = []

    try:

        if (dataset_type == "base") and (remote is True):
            columns = ["name", "eol"]
            resources = host.distribution.releases

        else:

            if (dataset_type == "base"):
                resources_class = iocage.Releases.ReleasesGenerator
                columns = ["full_name"]
            elif (dataset_type == "datasets"):
                resources_class = None
                columns = ["name", "dataset"]
                resources = [
                    dict(name=name, dataset=root_datasets.root.name)
                    for name, root_datasets
                    in host.datasets.items()
                ]
            else:
                resources_class = iocage.Jails.JailsGenerator
                columns = _list_output_comumns(output, _long)
                if dataset_type == "template":
                    filters += ("template=yes",)
                else:
                    filters += ("template=no,-",)

            if resources_class is not None:
                resources = resources_class(
                    logger=logger,
                    host=host,
                    zfs=ctx.parent.zfs,
                    # ToDo: allow quoted whitespaces from user inputs
                    filters=filters
                )

    except iocage.errors.IocageException:
        exit(1)

    if output_format == "list":
        _print_list(resources, columns, header, "\t")
    elif output_format == "csv":
        _print_list(resources, columns, header, ";")
    elif output_format == "json":
        _print_json(resources, columns)
    else:
        _print_table(resources, columns, header, _sort)


def _print_table(
    resources: typing.Generator[
        iocage.ListableResource.ListableResource,
        None,
        None
    ],
    columns: list,
    show_header: bool,
    sort_key: typing.Optional[str]=None
) -> None:

    table_data = []
    for resource in resources:
        table_data.append(_lookup_resource_values(resource, columns))

    print_table(table_data, columns, show_header, sort_key)


def _print_list(
    resources: typing.Generator[
        iocage.Jails.JailsGenerator,
        None,
        None
    ],
    columns: list,
    show_header: bool,
    separator: str=";"
) -> None:

    if show_header is True:
        print(separator.join(columns).upper())

    for resource in resources:
        print(separator.join(_lookup_resource_values(resource, columns)))


def _print_json(
    resources: typing.Generator[
        iocage.Jails.JailsGenerator,
        None,
        None
    ],
    columns: list,
    # json.dumps arguments
    indent: int=2,
    sort_keys: bool=True
) -> None:

    output = []
    for resource in resources:
        output.append(dict(zip(
            columns,
            _lookup_resource_values(resource, columns)
        )))

    print(json.dumps(
        output,
        indent=indent,
        sort_keys=sort_keys
    ))


def _lookup_resource_values(
    resource: 'iocage.Resource.Resource',
    columns: typing.List[str]
) -> typing.List[str]:
    if "getstring" in resource.__dir__():
        return list(map(
            lambda column: str(resource.getstring(column)),
            columns
        ))
    else:
        return list(map(
            lambda column: str(resource[column]),
            columns
        ))


def _list_output_comumns(
    user_input: typing.Optional[str]="",
    long_mode: bool=False
) -> typing.List[str]:

    if user_input is not None:
        return user_input.strip().split(',')
    else:
        columns = ["jid", "full_name"]

        if long_mode is True:
            columns += [
                "running",
                "release",
                "ip4_addr",
                "ip6_addr"
            ]
        else:
            columns += [
                "running",
                "release",
                "ip4_addr"
            ]

        return columns
