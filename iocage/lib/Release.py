import iocage.lib.helpers

import os
import tarfile
import libzfs
import urllib.request

class Release:

  def __init__(self, dataset=None, name=None, host=None, zfs=None):

    iocage.lib.helpers.init_zfs(self, zfs)
    iocage.lib.helpers.init_host(self, host)

    self.name = name
    self._dataset = None
    self.dataset = dataset
    
    self.assets = ["base"]

    if self.host.distribution.name != "HardenedBSD":
      self.assets.append("lib32")

  @property
  def dataset(self):
    if self._dataset == None:
      self._dataset = self.zfs.get_dataset(self.dataset_name)
    return self._dataset

  @dataset.setter
  def dataset(self, value):
    if isinstance(value, libzfs.ZFSDataset):
      try:
        value.mountpoint
      except:
        value.mount()

      self._dataset = value
      self._update_name_from_dataset()

    else:
      self._zfs = None

  @property
  def releases_folder(self):      
    return self.host.datasets.releases.mountpoint

  @property
  def download_directory(self):
    return f"{self.releases_folder}/{self.name}"

  @property
  def root_dir(self):
    try:
      return self.dataset.mountpoint
    except:
      return f"{self.releases_folder}/{self.name}/root"

  @property
  def remote_url(self):
    return f"{self.host.distribution.mirror_url}/{self.name}"      

  @property
  def available(self):
    try:
      request = urllib.request.Request(self.remote_url, method="HEAD")
      resource = urllib.request.urlopen(request)
      return resource.getcode() == 200
    except:
      return False

  @property
  def fetched(self):
    return os.path.isdir(self.root_dir)

  @property
  def zfs_pool(self):
    try:
      return self.host.datasets.releases.pool
    except:
      raise
      pass

    try:
      return self.dataset.pool
    except:
      pass

    raise Exception("Cannot find the ZFS pool without knowing the dataset or release_dataset")

  @property
  def dataset_name(self):
    return f"{self.host.datasets.releases.name}/{self.name}/root"

  def download(self):
    self._require_empty_root_dir()
    self._create_dataset()
    self._ensure_dataset_mounted()
    self._fetch_assets()
    self._extract_assets()
    self._cleanup()

  def _create_dataset(self):
    try:
      if isinstance(self.dataset, libzfs.ZFSDataset):
        return
    except:
      pass

    options = {
      "compression": "lz4"
    }
    self.zfs_pool.create(self.dataset_name, options, create_ancestors=True)
    self._dataset = self.zfs.get_dataset(self.dataset_name)

  def _ensure_dataset_mounted(self):
    if not self.dataset.mountpoint:
      self.dataset.mount()

  def _fetch_assets(self):
    for asset in self.assets:
      url = f"{self.remote_url}/{asset}.txz"
      path = self._get_asset_location(asset)

      if os.path.isfile(path):
        print(f"{path} already exists. Skipping download.")
        return
      else:
        print(f"Fetching {url}")
        urllib.request.urlretrieve(url, path)

  def _require_empty_root_dir(self):
    if os.path.isdir(self.root_dir) and os.listdir(self.root_dir) != []:
      raise Exception(f"The directory '{self.root_dir}' is not empty")

  def _get_asset_location(self, asset_name):
    return f"{self.download_directory}/{asset_name}.txz"

  def _extract_assets(self):
    for asset in self.assets:
      with tarfile.open(self._get_asset_location(asset)) as f:
        print(f"Verifying file structure in {asset}")
        self._check_tar_files(f.getmembers())
        print(f"Extracting {asset}")
        f.extractall(self.root_dir)

  def _update_name_from_dataset(self):
    if self.dataset:
      self.name = self.dataset.name.split("/")[-2:-1]

  def _cleanup(self):
    for asset in self.assets:
      os.remove(self._get_asset_location(asset))

  def _check_tar_files(self, tar_infos):
    for i in tar_infos:
      if i.name == ".":
        continue
      if not i.name.startswith("./"):
        print(i.name)
        raise Exception("Filenames in txz release files must be relative paths begining with './'")
      if ".." in i.name:
        raise Exceptions("FIlenames in txz release files must not contain '..'")
