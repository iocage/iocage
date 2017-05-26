"""df module for the cli."""

import click
import texttable

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc


@click.command(name="df", help="Show resource usage of all jails.")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--long", "-l", "_long", is_flag=True, default=False,
              help="Show the full uuid.")
@click.option("--sort", "-s", "_sort", default="tag", nargs=1,
              help="Sorts the list by the given type")
def cli(header, _long, _sort):
    """Allows a user to show resource usage of all jails."""
    table = texttable.Texttable(max_width=0)
    jail_list = ioc.IOCage().df(long=_long)

    sort = ioc_common.ioc_sort("df", _sort)
    jail_list.sort(key=sort)
    if header:
        jail_list.insert(0, ["UUID", "CRT", "RES", "QTA", "USE", "AVA", "TAG"])
        # We get an infinite float otherwise.
        table.set_cols_dtype(["t", "t", "t", "t", "t", "t", "t"])
        table.add_rows(jail_list)

        ioc_common.logit({
            "level"  : "INFO",
            "message": table.draw()
        })
    else:
        for jail in jail_list:
            ioc_common.logit({
                "level"  : "INFO",
                "message": "\t".join(jail)
            })
