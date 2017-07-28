import iocage.lib.helpers

import os
import sys
import tarfile
import hashlib
import libzfs
import urllib.request
import shutil

class Release:

  def __init__(self, name=None, dataset=None, host=None, zfs=None, logger=None, check_signatures=True):

    iocage.lib.helpers.init_logger(self, logger)
    iocage.lib.helpers.init_zfs(self, zfs)
    iocage.lib.helpers.init_host(self, host)

    self.name = name
    self._signatures = None
    self._dataset = None
    self.dataset = dataset
    self.check_signatures = (check_signatures == True)
    
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
  def base_dataset(self):
    # base datasets are created from releases. required to start zfs-basejails
    return self.zfs.get_dataset(self.base_dataset_name)

  @property
  def base_dataset_name(self):
    return f"{self.host.datasets.base.name}/{self.name}/root"

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

  @property
  def signatures(self):
    if not self._signatures:
      if not os.path.isfile(self.__get_signature_location()):
        self.logger.spam("Signatures have not yet been downloaded.")
        self._fetch_signatures()
      self._signatures = self.read_signatures()

    return self._signatures

  def fetch(self):
    self._require_empty_root_dir()
    self._create_dataset()
    self._ensure_dataset_mounted()
    self._fetch_assets()
    self._extract_assets()
    self._update_zfs_base()
    self._cleanup()

  """
  Depending on the version of iocage that was used the releases are stored
  in different formats. The most generic form is the to split it in multiple
  datasets that represent the basedir structure
  """
  def create_basejail_datasets(self):
    base_dataset = self.host.datasets.base

    if self._basejail_datasets_already_exists(self.name):
      return

    for basedir in iocage.lib.helper.get_basedir_list():
      self._create_dataset()


  def _basejail_datasets_already_exists(self, release_name):
    base_dataset = self.host.datasets.base
    for dataset in base_dataset.children:
      if dataset.name == f"{base_dataset.name}/release_name":
        return True
    return False

  def _create_dataset(self, name=None):

    if name == None:
      name = self.dataset_name

    try:
      if isinstance(self.dataset, libzfs.ZFSDataset):
        return
    except:
      pass

    options = {
      "compression": "lz4"
    }
    self.zfs_pool.create(name, options, create_ancestors=True)
    self._dataset = self.zfs.get_dataset(name)

  def _ensure_dataset_mounted(self):
    if not self.dataset.mountpoint:
      self.dataset.mount()

  def _fetch_signatures(self):
    url = f"{self.remote_url}/{self.host.distribution.signature_file}"
    path = self.__get_signature_location()
    self.logger.verbose(f"Downloading signatures from {url}")
    urllib.request.urlretrieve(url, path)
    self.logger.debug(f"Signature downloaded to {path}")

  def _fetch_assets(self):
    for asset in self.assets:
      url = f"{self.remote_url}/{asset}.txz"
      path = self._get_asset_location(asset)

      if os.path.isfile(path):
        self.logger.verbose(f"{path} already exists. Skipping download.")
        return
      else:
        self.logger.debug(f"Starting download of {url}")
        urllib.request.urlretrieve(url, path)
        self.logger.verbose(f"{url} was saved to {path}")

  def _require_empty_root_dir(self):
    if os.path.isdir(self.root_dir) and os.listdir(self.root_dir) != []:
      self.logger.error(f"The directory '{self.root_dir}' is not empty")
      sys.exit(1)

  def read_signatures(self):
    # yes, this can read HardenedBSD and FreeBSD signature files
    path = self.__get_signature_location()
    signatures = {}
    with open(path, "r") as f:
      for line in f.read().split("\n"):
        s = set(line.replace("\t", " ").split(" "))
        fingerprint = None
        asset = None
        for x in s:
          if len(x) == 64:
            fingerprint = x
          elif x.endswith(".txz"):
            asset = x[:-4]
        if asset and fingerprint:
          signatures[asset] = fingerprint
    count = len(signatures)
    self.logger.spam(f"{count} signatures read from {path}")
    return signatures

  def __get_signature_location(self):
    return f"{self.download_directory}/{self.host.distribution.signature_file}"

  def _get_asset_location(self, asset_name):
    return f"{self.download_directory}/{asset_name}.txz"

  def _extract_assets(self):

    for asset in self.assets:

      if self.check_signatures:
          self._check_asset_signature(asset)

      with tarfile.open(self._get_asset_location(asset)) as f:

        self.logger.verbose(f"Verifying file structure in {asset}")
        self._check_tar_files(f.getmembers())
          
        self.logger.debug(f"Extracting {asset}")
        f.extractall(self.root_dir)
        self.logger.verbose(f"Asset {asset} was extracted to {self.root_dir}")

  def _update_name_from_dataset(self):
    if self.dataset:
      self.name = self.dataset.name.split("/")[-2:-1]

  def _update_zfs_base(self):
     
    try:
      self.host.datasets.base.pool.create(self.base_dataset_name, {}, create_ancestors=True)
      self.base_dataset.mount()
    except:
      for child_dataset in  self.base_dataset.children:
        child_dataset.delete()

    base_dataset = self.base_dataset

    for folder in iocage.lib.helpers.get_basedir_list():
      self.host.datasets.base.pool.create(f"{self.base_dataset.name}/{folder}", {}, create_ancestors=True)
      self.zfs.get_dataset("{self.base_dataset.name}/{folder}").mount()

      src_path = f"{self.dataset.mountpoint}/{folder}"
      dst_path = f"{self.base_dataset.mountpoint}/{folder}"

      self.logger.verbose(f"Copying {folder} from {src_path} to {dst_path}")
      shutil.copytree(src_path, dst_path)

    self.logger.debug(f"Updated release base datasets for {self.name}")

  def _cleanup(self):
    for asset in self.assets:
      os.remove(self._get_asset_location(asset))

  def _check_asset_signature(self, asset_name):
    local_file_signature = self._read_asset_signature(asset_name)
    expected_signature = self.signatures[asset_name]
    has_valid_signature =  local_file_signature == expected_signature
    if not has_valid_signature:
      self.logger.warn(f"Asset {asset_name}.txz has an invalid signature (was '{local_file_signature}' but expected '{expected_signature}')")
      raise Exception("Invalid Signature")
    else:
      self.logger.spam(f"Asset {asset_name}.txz has a valid signature ({expected_signature})")

  def _read_asset_signature(self, asset_name):
    asset_location = self._get_asset_location(asset_name)
    sha256 = hashlib.sha256()
    with open(asset_location, 'rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            sha256.update(block)
    return sha256.hexdigest()

  def _check_tar_files(self, tar_infos):
    for i in tar_infos:
      if i.name == ".":
        continue
      if not i.name.startswith("./"):
        raise Exception("Filenames in txz release files must be relative paths begining with './'")
      if ".." in i.name:
        raise Exceptions("FIlenames in txz release files must not contain '..'")
