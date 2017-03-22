"""deactivate module for the cli."""
from subprocess import CalledProcessError, PIPE, check_call

import click

import iocage.lib.ioc_log as ioc_log

__cmdname__ = "deactivate_cmd"
__rootcmd__ = True


@click.command(name="deactivate", help="Set a zpool inactive for iocage" +
                                       " usage.")
@click.argument("zpool")
def deactivate_cmd(zpool):
    """Calls ZFS set to change the property org.freebsd.ioc:active to no."""
    lgr = ioc_log.getLogger('ioc_cli_deactivate')

    try:
        check_call(["zfs", "set", "org.freebsd.ioc:active=no", zpool],
                   stderr=PIPE, stdout=PIPE)
        lgr.info("{} successfully deactivated.".format(zpool))
    except CalledProcessError:
        raise RuntimeError("Pool: {} does not exist!".format(zpool))
