import iocage.lib.helpers

import libzfs

class Datasets:

  def __init__(self, root_dataset=None, zfs=None):
    iocage.lib.helpers.init_zfs(self, zfs)

    self._releases_dataset = None

    if(isinstance(root_dataset, libzfs.ZFSDataset)):
      self.root_dataset = root_dataset
    else:
      try:
        self.root_dataset = self.zfs.get_dataset_by_path("/iocage")
      except:
        raise Exception(
          "root_dataset was not specified and no dataset is "
          "mounted as /iocage. Is iocage activated?"
        )

  @property
  def releases_dataset(self):

    if not self._releases_dataset:
      name = f"{self.root_dataset.name}/releases"
      releases_dataset = self.zfs.get_dataset(name)
      self._releases_dataset = releases_dataset
    
    return self._releases_dataset
