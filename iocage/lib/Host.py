import iocage.lib.Distribution
import iocage.lib.Datasets
import iocage.lib.helpers

import os
import platform
import libzfs

class Host:

  def __init__(self, root_dataset=None, zfs=None):

    iocage.lib.helpers.init_zfs(self, zfs)
    self.datasets = iocage.lib.Datasets.Datasets(root_dataset=root_dataset)
    self.distribution = iocage.lib.Distribution.Distribution(host=self)
    
    self.releases_dataset = None

  @property
  def userland_version(self):
    return float(os.uname()[2].partition("-")[0])

  @property
  def processor(self):
    return platform.processor()
