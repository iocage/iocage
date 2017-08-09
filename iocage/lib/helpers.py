import iocage.lib.Host
import iocage.lib.Datasets
import iocage.lib.Logger

import libzfs
import subprocess


def init_zfs(self, zfs):
    if isinstance(zfs, libzfs.ZFS):
        self.zfs = zfs
    else:
        self.zfs = get_zfs()


def get_zfs():
    return libzfs.ZFS(history=True, history_prefix="<iocage>")


def init_host(self, host=None):

    if host:
        self.host = host
    else:
        try:
            logger = self.logger
        except:
            logger = None

        self.host = iocage.lib.Host.Host(logger=logger)


def init_datasets(self, datasets=None):
    if datasets:
        self.datasets = datasets
    else:
        self.datasets = iocage.lib.Datasets.Datasets()


def init_logger(self, logger=None):
    if logger is not None:
        object.__setattr__(self, 'logger', logger)
    else:
        new_logger = iocage.lib.Logger.Logger()
        object.__setattr__(self, 'logger', new_logger)


def exec(command, logger=None, ignore_error=False):

    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)

    if logger:
        logger.log(f"Executing: {command_str}", level="spam")

    child = subprocess.Popen(
        command,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    stdout, stderr = child.communicate()
    stdout = stdout.decode("UTF-8").strip()
    stderr = stderr.decode("UTF-8").strip()

    if logger and stdout:
        logger.spam(_prettify_output(stdout))

    if child.returncode > 0:

        if logger:
            log_level = "spam" if ignore_error else "warning"
            logger.log(
                f"Command exited with {child.returncode}: {command_str}",
                level=log_level
            )
            if stderr:
                logger.log(_prettify_output(stderr), level=log_level)

        if ignore_error is False:
            raise Exception(f"Command exited with {child.returncode}")

    return child, stdout, stderr


def _prettify_output(output):
    return "\n".join(map(
        lambda line: f"    {line}",
        output.split("\n")
    ))


def exec_passthru(command, logger=None):

    if isinstance(command, str):
        command = [command]

    command_str = " ".join(command)
    if logger:
        logger.log(f"Executing (interactive): {command_str}", level="spam")

    return subprocess.Popen(command).communicate()


def shell(command, logger=None):
    if not isinstance(command, str):
        command = " ".join(command)

    if logger:
        logger.log(f"Executing Shell: {command}", level="spam")

    return subprocess.check_output(
        command,
        shell=True,
        universal_newlines=True,
        stderr=subprocess.DEVNULL
    )


# ToDo: replace with (u)mount library
def umount(mountpoint, force=False, ignore_error=False, logger=None):

    cmd = ["/sbin/umount"]

    if force is True:
        cmd.append("-f")

    cmd.append(mountpoint)

    try:
        exec(cmd)
        if logger is not None:
            logger.debug(
                f"Jail mountpoint {mountpoint} umounted"
            )
    except:
        if logger is not None:
            logger.spam(
                f"Jail mountpoint {mountpoint} not unmounted"
            )
        if ignore_error is False:
            raise


def get_basedir_list():
    return [
        "bin",
        "boot",
        "lib",
        "libexec",
        "rescue",
        "sbin",
        "usr/bin",
        "usr/include",
        "usr/lib",
        "usr/libexec",
        "usr/sbin",
        "usr/share",
        "usr/libdata",
        "usr/lib32"
    ]
