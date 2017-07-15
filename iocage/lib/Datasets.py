import iocage.lib.helpers

import libzfs

class Datasets:

  def __init__(self, root=None, zfs=None, logger=None):
    #iocage.lib.helpers.init_logger(self, logger)
    iocage.lib.helpers.init_zfs(self, zfs)

    self._datasets = {}

    if(isinstance(root, libzfs.ZFSDataset)):
      self.root = root
    else:
      try:
        self.root = self.zfs.get_dataset_by_path("/iocage")
      except:
        raise Exception(
          "root_dataset was not specified and no dataset is "
          "mounted as /iocage. Is iocage activated?"
        )

  @property
  def releases(self):
    return self._get_or_create_dataset("releases")

  @property
  def base(self):
    return self._get_or_create_dataset("base")

  @property
  def jails(self):
    return self._get_or_create_dataset("jails")

  def _get_or_create_dataset(self, name):

    try:
      return self.datasets[name]
    except:
      pass

    name = f"{self.root.name}/{name}"
    try:
      dataset = self.zfs.get_dataset(name)
    except:
      self.root.pool.create(name, {})
      dataset = self.zfs.get_dataset(name)
      dataset.mount()
    self._datasets[name] = dataset

    return dataset

