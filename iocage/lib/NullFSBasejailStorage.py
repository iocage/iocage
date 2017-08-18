import iocage.lib.StandaloneJailStorage
import iocage.lib.helpers


class NullFSBasejailStorage:

    def apply(self, release=None):
        NullFSBasejailStorage._create_nullfs_directories(self)

    def setup(self, release):
        iocage.lib.StandaloneJailStorage.StandaloneJailStorage.setup(
            self, release)

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

    def _create_nullfs_directories(self):
        for basedir in iocage.lib.helpers.get_basedir_list() + ["dev", "etc"]:
            self.create_jail_mountpoint(basedir)
