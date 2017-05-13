"""clone module for the cli."""
import click
import iocage.lib.iocage as ioc
import iocage.lib.ioc_common as ioc_common

__rootcmd__ = True


@click.command(name="clone", help="Clone a jail.")
@click.argument("source", nargs=1)
@click.argument("props", nargs=-1)
def cli(source, props):
    err, msg = ioc.IOCage(jail=source).create(source, props, clone=True)

    if err:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": msg
        })
