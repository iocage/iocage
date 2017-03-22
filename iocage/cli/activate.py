"""activate module for the cli."""
from subprocess import PIPE, Popen
import iocage.lib.ioc_log as ioc_log

import click

__cmdname__ = "activate_cmd"
__rootcmd__ = True

IOCAGE_ZFS_ACTIVE_PROPERTY = "org.freebsd.ioc:active"

lgr = ioc_log.getLogger('ioc_cli_activate')


def get_zfs_pools():
    """
    Returns all the ZFS pools available on the system
    :rtype: list of strings
    :raise RuntimeError: if the underlying zfs command returns errors
    """
    proc = Popen(["zpool", "list", "-H", "-o", "name"], stdout=PIPE,
                 stderr=PIPE)
    stdout_data, stderr_data = proc.communicate()

    if stderr_data:
        raise RuntimeError("Cannot get the list of available ZFS pools:"
                           f" {stderr_data.decode('utf-8')}")

    return stdout_data.decode('utf-8').split()


def set_zfs_pool_active_property(zpool_name, activate=True):
    """
    Set or unset the IOCAGE_ACTIVE_PROPERTY property
    on a ZFS pool for iocage usage
    :param zpool_name: name of the ZFS pool
    :param activate: if True set the property to "yes", to "no" otherwise
    :type zpool_name: string
    :type activate: bool
    :raises RuntimeError: if the zfs command returns errors
    :raises ValueError: if one parameter is incorrect
    """

    if not isinstance(zpool_name, str) or zpool_name == "":
        raise ValueError("'zpool_name' must be a non-empty string")

    if not isinstance(activate, bool):
        raise ValueError("'activate' must be a boolean")

    zfs_cmd = ["zfs", "set"]

    if activate:
        zfs_cmd.append(f"{IOCAGE_ZFS_ACTIVE_PROPERTY}=yes")
    else:
        zfs_cmd.append(f"{IOCAGE_ZFS_ACTIVE_PROPERTY}=no")

    zfs_cmd.append(zpool_name)
    proc = Popen(zfs_cmd, stdout=PIPE, stderr=PIPE)
    stdout_data, stderr_data = proc.communicate()

    if stderr_data:
        if activate:
            raise RuntimeError(f"Cannot activate ZFS pool '{zpool_name}':"
                               f" {stderr_data.decode('utf-8')}")
        else:
            raise RuntimeError(f"Cannot deactivate ZFS pool '{zpool_name}':"
                               f" {stderr_data.decode('utf-8')}")


def set_zfs_pool_comment(zpool_name, comment):
    """
    Set the ZFS pool comment
    :param zpool_name: name of ZFS pool name
    :param comment: the comment to set
    :type zpool_name: string
    :type comment: string
    :raises RuntimeError: if the zpool command returns an error
    :raises ValueError: if parameters are incorrect
    """

    if not isinstance(zpool_name, str) or zpool_name == "":
        raise ValueError("'zpool_name' must be a non-empty string")

    if not isinstance(comment, str) or comment == "":
        raise ValueError("'comment' must be a non-empty string")

    zfs_cmd = ["zpool", "set", f"comment={comment}", zpool_name]
    proc = Popen(zfs_cmd, stdout=PIPE, stderr=PIPE)
    stdout_data, stderr_data = proc.communicate()

    if stderr_data:
        raise RuntimeError(f"Cannot set zpool comment to '{comment}' on ZFS"
                           f" pool '{zpool_name}':"
                           f" {stderr_data.decode('utf-8')}")


@click.command(name="activate", help="Set a zpool active for iocage usage.")
@click.argument("zpool")
@click.option("--force", "-f", help="Will deactivate all other pools.",
              is_flag=True)
def activate_cmd(zpool, force):
    """Calls ZFS set to change the property org.freebsd.ioc:active to yes."""

    if force:
        lgr.info("'--force' specified, all other ZFS pools will be"
                 " deactivated for iocage usage")
        # Here we just want one active pool, so we 'deactivate' all
        # the ZFS pools, to ensure only one stays 'activated'
        zpools = get_zfs_pools()
        for pool in zpools:
            set_zfs_pool_active_property(pool, activate=False)

            # Check and clean if necessary iocage_legacy way
            # to mark a ZFS pool as usable (now replaced by ZFS property)
            proc = Popen(
                ["zpool", "get", "-H", "-o", "value", "comment", pool],
                stdout=PIPE, stderr=PIPE)
            stdout_data, stderr_data = proc.communicate()
            if stderr_data:
                raise RuntimeError("Cannot retrieve comment for ZFS pool "
                                   f"'{zpool}': {stderr_data.decode('utf-8')}")

            comment = stdout_data.decode('utf-8').strip()

            if comment == "iocage":
                set_zfs_pool_comment(zpool, "-")

    set_zfs_pool_active_property(zpool, activate=True)
    lgr.info(f"ZFS pool '{zpool}' successfully activated.")
