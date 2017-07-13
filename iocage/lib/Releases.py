#import iocage.lib.Release
import iocage.lib.helpers

class Releases:

  def __init__(self, dataset, host=None):
    iocage.lib.helpers.init_host(self, host)
    self.dataset = dataset

  @property
  def local(self):
    release_datasets = self.dataset.children
    return map(lambda x: x.name.split("/").pop(), release_datasets)

  @property
  def available_releases(self):
    return self.host.distribution.releases  
  
  @property
  def releases_folder(self):
    return self.dataset.mountpoint
