"""chroot module for the cli."""
from subprocess import PIPE, Popen
import iocage.lib.ioc_logger as ioc_logger

import click

from iocage.lib.ioc_list import IOCList

__cmdname__ = "chroot_cmd"
__rootcmd__ = True


def mount(path, _type):
    if _type == "devfs":
        cmd = ["mount", "-t", "devfs", "devfs", path]
    else:
        cmd = ["mount", "-a", "-F", path]

    _, stderr = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()

    return stderr


def umount(path, _type):
    if _type == "devfs":
        cmd = ["umount", path]
    else:
        cmd = ["umount", "-a", "-F", path]

    _, stderr = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()

    return stderr


@click.command(context_settings=dict(
    ignore_unknown_options=True, ),
    name="chroot", help="Chroot to a jail.")
@click.argument("jail")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def chroot_cmd(jail, command):
    """Will chroot into a jail regardless if it's running."""
    lgr = ioc_logger.Logger('ioc_cli_chroot')
    lgr = lgr.getLogger()
    jails, paths = IOCList("uuid").list_datasets()
    command = list(command)

    # We may be getting ';', '&&' and so forth. Adding the shell for safety.
    if len(command) == 1:
        command = ["/bin/sh", "-c"] + command

    if jail.startswith("-"):
        raise RuntimeError("Please specify a jail first!")

    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]

    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.items()):
            lgr.critical("  {} ({})".format(u, t))
        exit(1)
    else:
        lgr.critical("{} not found!".format(jail))
        exit(1)

    devfs_stderr = mount(f"{path}/root/dev", "devfs")

    if devfs_stderr:
        lgr.critical("Mounting devfs failed!")
        exit(1)

    fstab_stderr = mount(f"{path}/fstab", "fstab")

    if fstab_stderr:
        lgr.critical("Mounting devfs failed!")
        exit(1)

    chroot = Popen(["chroot", f"{path}/root"] + command)
    chroot.communicate()

    udevfs_stderr = umount(f"{path}/root/dev", "devfs")
    if udevfs_stderr:
        lgr.critical("Unmounting devfs failed!")
        exit(1)

    ufstab_stderr = umount(f"{path}/fstab", "fstab")
    if ufstab_stderr:
        if b"fstab reading failure\n" in ufstab_stderr:
            # By default our fstab is empty and will throw this error.
            pass
        else:
            lgr.critical("Unmounting fstab failed!")
            exit(1)

    if chroot.returncode:
        lgr.warning("Chroot had a non-zero exit code!")
