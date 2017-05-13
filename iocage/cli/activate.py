"""activate module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="activate", help="Set a zpool active for iocage usage.")
@click.argument("zpool")
def cli(zpool):
    """Calls ZFS set to change the property org.freebsd.ioc:active to yes."""
    ioc.IOCage(activate=True).activate(zpool)

    ioc_common.logit({
        "level"  : "INFO",
        "message": f"ZFS pool '{zpool}' successfully activated."
    })
