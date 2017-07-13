import iocage.lib.Host
import iocage.lib.Datasets

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
    self.datsets = iocage.lib.Datasets.Datasets()

def exec(command):

  if isinstance(command, str):
    command = [command]

  command_str = " ".join(command)
  print(f"Executing: {command_str}")
  return subprocess.check_output(command, shell=False, stderr=subprocess.DEVNULL)

def shell(command):
  if not isinstance(command, str):
    command = " ".join(command)

  print(f"Executing Shell: {command}")
  return subprocess.check_output(command, shell=True, universal_newlines=True, stderr=subprocess.DEVNULL)
