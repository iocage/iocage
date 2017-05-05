"""list module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_fetch as ioc_fetch
import iocage.lib.ioc_list as ioc_list


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
def cli(dataset_type, header, _long, remote, http, plugins, _sort):
    """This passes the arg and calls the jail_datasets function."""
    freebsd_version = ioc_common.checkoutput(["freebsd-version"])

    if dataset_type is None:
        dataset_type = "all"

    if remote:
        if "HBSD" in freebsd_version:
            hardened = True
        else:
            hardened = False

        ioc_fetch.IOCFetch("", http=http, hardened=hardened).fetch_release(
            _list=True)
    elif plugins:
        ioc_fetch.IOCFetch("").fetch_plugin_index("", _list=True)
    else:
        _list = ioc_list.IOCList(dataset_type, header, _long,
                                 _sort).list_datasets()

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
