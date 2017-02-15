"""activate module for the cli."""
import logging
from subprocess import CalledProcessError, PIPE, Popen, check_call

import click

__cmdname__ = "activate_cmd"
__rootcmd__ = True


@click.command(name="activate", help="Set a zpool active for iocage usage.")
@click.argument("zpool")
@click.option("--force", "-f", help="Will deactivate all other pools.",
              is_flag=True)
def activate_cmd(zpool, force):
    """Calls ZFS set to change the property org.freebsd.ioc:active to yes."""
    lgr = logging.getLogger('ioc_cli_activate')

    try:
        if force:
            zpools = Popen(["zpool", "list", "-H", "-o", "name"],
                           stdout=PIPE).communicate()[0].split()

            for zfs in zpools:
                # If they specify force we just want one active pool.
                check_call(["zfs", "set", "org.freebsd.ioc:active=no", zfs],
                           stderr=PIPE, stdout=PIPE)

        check_call(["zfs", "set", "org.freebsd.ioc:active=yes", zpool],
                   stderr=PIPE, stdout=PIPE)
        lgr.info("{} successfully activated.".format(zpool))
    except CalledProcessError:
        raise RuntimeError("Pool: {} does not exist!".format(zpool))
