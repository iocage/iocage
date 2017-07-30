import helpers

class ZFSBasejailStorage:

  def prepare(self):

    release = self.jail.config.release
    root_dataset = self.get_or_create_jail_root_dataset()

    self._delete_clone_target_datasets()

  def apply(self, release=None):
    release = release if release else self.jail.cloned_release
    return ZFSBasejailStorage.clone(self, release)

  def clone(self, release):

    if not self.jail.config.basejail_type == "zfs":
      raise Exception(f"Jail {self.jail.humanreadable_name} is not a zfs basejail.")

    for basedir in helpers.get_basedir_list():
      source_dataset_name = f"{release.base_dataset.name}/{basedir}"
      target_dataset_name = f"{self.jail_root_dataset_name}/{basedir}"
      self.clone_zfs_dataset(source_dataset_name, target_dataset_name)

  def _delete_clone_target_datasets(self, root=None):

    if root == None:
      root = list(self.jail_root_dataset.children)

    for child in root:
      relative_name = child.name.replace(f"{self.jail_root_dataset_name}/","")
      basedirs = helpers.get_basedir_list()

      if relative_name in basedirs:

        # Unmount if mounted
        try:
          current_mountpoint = child.mountpoint
          if current_mountpoint:
            child.umount()
            self.logger.verbose(f"Clone target {current_mountpoint} unmounted")
        except:
          pass

        # Delete existing snapshots
        for snapshot in child.snapshots:
          try:
            snapshot_name = snapshot.name
            snapshot.delete()
            self.logger.verbose(f"Snapshot {current_mountpoint} deleted")
          except:
            pass

        child.delete()

      else:
        self._delete_clone_target_datasets(list(child.children))
