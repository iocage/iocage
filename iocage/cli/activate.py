"""CLI command to activate a zpool."""
import logging
from subprocess import CalledProcessError, PIPE, check_call

import click

__cmdname__ = "activate_cmd"
__rootcmd__ = True


@click.command(name="activate", help="Set a zpool active for iocage usage.")
@click.argument("zpool")
def activate_cmd(zpool):
    """Calls ZFS set to change the property org.freebsd.ioc:active to yes."""
    lgr = logging.getLogger('ioc_cli_activate')

    try:
        check_call(["zfs", "set", "org.freebsd.ioc:active=yes", zpool],
                   stderr=PIPE, stdout=PIPE)
        lgr.info("{} successfully activated.".format(zpool))
    except CalledProcessError:
        raise RuntimeError("Pool: {} does not exist!".format(zpool))
