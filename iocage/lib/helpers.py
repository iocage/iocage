import iocage.lib.Host
import iocage.lib.Datasets
import iocage.lib.Logger

import libzfs
import subprocess

def init_zfs(self, zfs):
  if isinstance(zfs, libzfs.ZFS):
    self.zfs = zfs
  else:
    self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

def init_host(self, host=None):
  if host:
    self.host = host
  else:
    self.host = iocage.lib.Host.Host()

def init_datasets(self, datasets=None):
  if datasets:
    self.datasets = datasets
  else:
    self.datasets = iocage.lib.Datasets.Datasets()

def init_logger(self, logger=None):
  if logger:
    object.__setattr__(self, 'logger', logger)
  else:
    new_logger = iocage.lib.Logger.Logger()
    object.__setattr__(self, 'logger', new_logger)

def exec(command, logger=None):

  if isinstance(command, str):
    command = [command]

  command_str = " ".join(command)
  if logger:
    self.logger.log(f"Executing: {command_str}", level="spam")
  return subprocess.check_output(command, shell=False, stderr=subprocess.DEVNULL)

def shell(command, logger=None):
  if not isinstance(command, str):
    command = " ".join(command)

  if logger:
    self.logger.log(f"Executing Shell: {command}", level="spam")
  return subprocess.check_output(command, shell=True, universal_newlines=True, stderr=subprocess.DEVNULL)

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
