import iocage.lib.helpers

import libzfs

class Datasets:

  def __init__(self, root=None, zfs=None):
    iocage.lib.helpers.init_zfs(self, zfs)

    self._releases_dataset = None

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

    if not self._releases_dataset:
      name = f"{self.root.name}/releases"
      releases_dataset = self.zfs.get_dataset(name)
      self._releases_dataset = releases_dataset
    
    return self._releases_dataset
