class ZFSShareStorage:

  def mount_zfs_shares(self, auto_create=False):
      self.logger.log("Mounting ZFS shares")
      self._mount_procfs()
      self._mount_jail_datasets(auto_create=auto_create)

  def get_zfs_datasets(self, auto_create=None):
    dataset_names = self.jail.config.jail_zfs_dataset
    dataset_not_found_error = False

    auto_create = self.auto_create if auto_create == None else auto_create

    datasets = set()
    for name in dataset_names:

      zpool = None
      try:
        zpool = self._get_pool_from_dataset_name(name)
      except:
        pass

      try:
        # legacy support (datasets not prefixed with pool/)
        zpool = self._get_pool_from_dataset_name(f"{self.jail.zfs_pool_name}/{name}")
        name = f"{self.jail.zfs_pool_name}/{name}"
      except:

        pass

      try:
        if auto_create:
          zpool.create(name, {}, create_ancestors=True)
      except Exception as e:
        print(e)
        pass
      
      try:
        dataset = self.zfs.get_dataset(name)
        datasets.add(dataset);
      except:
        raise Exception(f"Neither the dataset {name} nor {self.jail.zfs_pool_name}/{name} could be found")

    return datasets

  def _mount_jail_dataset(self, dataset_name):
    self.jail.exec(['zfs', 'mount', dataset_name])
