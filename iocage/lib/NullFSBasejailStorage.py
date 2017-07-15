import iocage.lib.StandaloneJailStorage
import iocage.lib.helpers

import os

class NullFSBasejailStorage:

  def apply(self, release=None):

    NullFSBasejailStorage.umount_nullfs(self)
    NullFSBasejailStorage.create_nullfs_directories(self)

  def setup(self, release):
    iocage.lib.StandaloneJailStorage.setup(self, release)

  """
  In preparation of starting the jail with nullfs mounts
  all mountpoints that are listed in fstab need to be unmounted
  """
  def umount_nullfs(self):

    with open(f"{self.jail.path}/fstab") as f:
      mounts = []
      for mount in f.read().splitlines():
        try:
          mounts.append(mount.replace("\t", " ").split(" ")[1])
        except:
          pass

      if (len(mounts) > 0):
        try:
          iocage.lib.helpers.exec(["umount"] + mounts)
        except:
          # in case directories were not mounted
          pass

  def create_nullfs_directories(self):
    basedirs = iocage.lib.helpers.get_basedir_list() + ["dev", "etc"]
    jail_root = self.jail_root_dataset.mountpoint

    for basedir in basedirs:
      basedir = f"{jail_root}/{basedir}"
      if not os.path.isdir(basedir):
        self.logger.verbose(f"Creating nullfs mountpoint {basedir}")
        os.makedirs(basedir)
