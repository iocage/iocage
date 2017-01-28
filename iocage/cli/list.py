"""
List module for the cli.
"""
import click

from iocage.lib.ioc_list import IOCList

__cmdname__ = "list_cmd"


@click.command(name="list", help="List a specified dataset type")
@click.option("--release", "--base", "-r", "-b", "dataset_type",
              flag_value="base", help="List all bases.")
@click.option("--template", "-t", "dataset_type", flag_value="template",
              help="List all templates.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full uuid and ip4 address.")
def list_cmd(dataset_type, header, _long):
    """This passes the arg and calls the jail_datasets function."""
    if dataset_type is None:
        dataset_type = "all"
    IOCList(dataset_type, header, _long).list_datasets()
