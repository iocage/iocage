"""list module for the cli."""
import click

from iocage.lib.ioc_common import checkoutput, logit
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
@click.option("--http", default=False,
              help="Have --remote use HTTP instead.", is_flag=True)
@click.option("--sort", "-s", "_sort", default="tag", nargs=1,
              help="Sorts the list by the given type")
def list_cmd(dataset_type, header, _long, remote, http, plugins, _sort):
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
        _list = IOCList(dataset_type, header, _long, _sort).list_datasets()

        if not header:
            if dataset_type == "base":
                for item in _list:
                    logit({
                        "level"  : "INFO",
                        "message": item
                    })
            else:
                for item in _list:
                    logit({
                        "level"  : "INFO",
                        "message": "\t".join(item)
                    })
        else:
            logit({
                "level"  : "INFO",
                "message": _list
            })
