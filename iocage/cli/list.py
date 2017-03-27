"""list module for the cli."""
import click

from iocage.lib.ioc_common import checkoutput
from iocage.lib.ioc_fetch import IOCFetch
from iocage.lib.ioc_list import IOCList

__cmdname__ = "list_cmd"


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
@click.option("--http", "-h", default=False,
              help="Have --remote use HTTP instead.", is_flag=True)
def list_cmd(dataset_type, header, _long, remote, http, plugins):
    """This passes the arg and calls the jail_datasets function."""
    freebsd_version = checkoutput(["freebsd-version"])

    if dataset_type is None:
        dataset_type = "all"

    if remote:
        if "HBSD" in freebsd_version:
            hardened = True
        else:
            hardened = False

        IOCFetch("", http=http, hardened=hardened).fetch_release(
            _list=True)
    elif plugins:
        IOCFetch("").fetch_plugin_index("", _list=True)
    else:
        _list = IOCList(dataset_type, header, _long).list_datasets()

        if not header:
            if dataset_type == "base":
                for item in _list:
                    print(item)
            else:
                for item in _list:
                    print("\t".join(item))
        else:
            print(_list)
