"""chroot module for the cli."""
import subprocess as su

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_list as ioc_list

__rootcmd__ = True


def mount(path, _type):
    if _type == "devfs":
        cmd = ["mount", "-t", "devfs", "devfs", path]
    else:
        cmd = ["mount", "-a", "-F", path]

    _, stderr = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

    return stderr


def umount(path, _type):
    if _type == "devfs":
        cmd = ["umount", path]
    else:
        cmd = ["umount", "-a", "-F", path]

    _, stderr = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

    return stderr


@click.command(context_settings=dict(
    ignore_unknown_options=True, ),
    name="chroot", help="Chroot to a jail.")
@click.argument("jail")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def cli(jail, command):
    """Will chroot into a jail regardless if it's running."""
    jails, paths = ioc_list.IOCList("uuid").list_datasets()
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
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for t, u in sorted(_jail.items()):
            ioc_common.logit({
                "level"  : "INFO",
                "message": f"  {u} ({t})"
            })
        exit(1)
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
        exit(1)

    devfs_stderr = mount(f"{path}/root/dev", "devfs")

    if devfs_stderr:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Mounting devfs failed!"
        })
        exit(1)

    fstab_stderr = mount(f"{path}/fstab", "fstab")

    if fstab_stderr:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Mounting fstab failed!"
        })
        exit(1)

    chroot = su.Popen(["chroot", f"{path}/root"] + command)
    chroot.communicate()

    udevfs_stderr = umount(f"{path}/root/dev", "devfs")
    if udevfs_stderr:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Unmounting devfs failed!"
        })
        exit(1)

    ufstab_stderr = umount(f"{path}/fstab", "fstab")
    if ufstab_stderr:
        if b"fstab reading failure\n" in ufstab_stderr:
            # By default our fstab is empty and will throw this error.
            pass
        else:
            ioc_common.logit({
                "level"  : "ERROR",
                "message": "Unmounting fstab failed!"
            })
            exit(1)

    if chroot.returncode:
        ioc_common.logit({
            "level"  : "WARNING",
            "message": "Chroot had a non-zero exit code!"
        })
