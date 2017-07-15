import iocage.lib.helpers

import libzfs
import pwd
import grp
import os


class Storage:

  def __init__(self, jail, zfs=None, auto_create=False, safe_mode=True, fsopts={}, logger=None):

    iocage.lib.helpers.init_logger(self, logger)
    iocage.lib.helpers.init_zfs(self, zfs)

    self.jail = jail

    # when auto_create is enabled, non-existing zfs volumes will be automatically created
    # if not enabled, accessing non-existent datasets will raise an error
    self.auto_create = auto_create

    # safe-mody only attaches zfs datasets to jails that were tagged with jailed=on already exist
    self.safe_mode = safe_mode

    # additional fsopts
    self._set_fsopts(fsopts)

  @property
  def zfs_enabled(self):
    try:
      return self.jail.config.jail_zfs == True
    except:
      return False

  @property
  def zfs_datasets(self):
    return self.get_zfs_datasets(self.auto_create)

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
          zpool.create(name, self.fsopts, create_ancestors=True)
      except Exception as e:
        print(e)
        pass
      
      try:
        dataset = self.zfs.get_dataset(name)
        datasets.add(dataset);
      except:
        raise Exception(f"Neither the dataset {name} nor {self.jail.zfs_pool_name}/{name} could be found")

    return datasets

  @property
  def jail_root_dataset(self):
    return self.zfs.get_dataset(self.jail_root_dataset_name)

  @property
  def jail_root_dataset_name(self):
    return f"{self.jail.dataset.name}/root"

  @property
  def _pool(self):
    return self.jail.host.datasets.root.pool

  def mount_zfs_shares(self, auto_create=False):
    if self.zfs_enabled:
      self._mount_procfs()
      self._mount_jail_datasets(auto_create=auto_create)

  def _delete_clone_target_datasets(self, root=None):

    if root == None:
      root = list(self.jail_root_dataset.children)

    basedirs = iocage.lib.helpers.get_basedir_list()

    for child in root:
      relative_name = child.name.replace(f"{self.jail_root_dataset_name}/","")

      if relative_name in basedirs:

        # Unmount if mounted
        try:
          child.umount()
        except:
          pass

        # Delete existing snapshots
        for snapshot in child.snapshots:
          try:
            snapshot.delete()
          except:
            pass

        child.delete()

      else:
        self._delete_clone_target_datasets(list(child.children))


  def clone_zfs_basejail(self, release):
    if not self.jail.config.basejail_type == "zfs":
      raise Exception(f"Jail {self.jail.humanreadable_name} is not a zfs basejail.")

    self._delete_clone_target_datasets()

    for basedir in iocage.lib.helpers.get_basedir_list():
      source_dataset_name = f"{release.base_dataset.name}/{basedir}"
      target_dataset_name = f"{self.jail_root_dataset_name}/{basedir}"
      self._clone_zfs_dataset(source_dataset_name, target_dataset_name)

  def clone_release(self, release):
    self._clone_zfs_dataset(release.dataset, self.jail_root_dataset_name)

  def _clone_zfs_dataset(self, source, target):

    snapshot_name = f"{source}@{self.jail.uuid}"

    # delete existing snapshot if existing
    existing_snapshot = None
    try:
      existing_snapshot = self.zfs.get_snapshot(snapshot_name)
    except:
      pass

    if existing_snapshot:
      existing_snapshot.delete()

    # snapshot release
    self.zfs.get_dataset(source).snapshot(snapshot_name)
    snapshot = self.zfs.get_snapshot(snapshot_name)

    # clone snapshot
    try:
      snapshot.clone(target)
    except:
      parent = "/".join(basedir.split("/")[:-1])
      pool = self.jail.host.datasets.root.pool
      pool.create(parent, {}, recursive=True)
      snapshot.clone(target)

    target_dataset = self.zfs.get_dataset(target)
    target_dataset.mount()
    self.logger.log(f"Cloned to {target}")

  def create_jail_dataset(self):
    self._create_dataset(self.jail.dataset_name)

  def create_jail_root_dataset(self):
    self._create_dataset(self.jail_root_dataset_name)

  def _create_dataset(self, name, mount=True):
    self._pool.create(name, {}, create_ancestors=True)
    if mount:
      ds = self.zfs.get_dataset(name)
      ds.mount()

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

  def create_nullfs_directories(self):
    basedirs = iocage.lib.helpers.get_basedir_list() + ["dev", "etc"]
    jail_root = self.jail_root_dataset.mountpoint

    for basedir in basedirs:
      basedir = f"{jail_root}/{basedir}"
      if not os.path.isdir(basedir):
        self.logger.verbose(f"Creating nullfs mountpoint {basedir}")
        os.makedirs(basedir)

  def _require_datasets_exist_and_jailed(self):
    existing_datasets = self.get_zfs_datasets(auto_create=False)
    for existing_dataset in existing_datasets:
        if existing_dataset.properties["jailed"] != "on":
          raise("Dataset {existing_dataset.name} is not jailed. Run 'zfs set jailed=on {existing_dataset.name}' to allow mounting")

  def _mount_jail_datasets(self, auto_create=None):
    
    auto_create = self.auto_create if auto_create == None else (auto_create == True)

    if self.safe_mode:
      self._require_datasets_exist_and_jailed()

    for dataset in self.zfs_datasets:

      self._unmount_local(dataset);

      # ToDo: bake jail feature into py-libzfs
      iocage.lib.helpers.exec(["zfs", "jail", self.jail.identifier, dataset.name])

      if dataset.properties['mountpoint']:
        for child in list(dataset.children):
          self._ensure_dataset_exists(child)
          self._mount_jail_dataset(child.name)

  def _mount_procfs(self):
    try:
      if jail.config.mount_procfs:
        iocage.lib.helpers.exec([
          "mount"
          "-t",
          "procfs"
          "proc"
          f"{self.path}/root/proc"
        ])
    except:
      pass

  def _mount_linprocfs(self):
    try:
      if not jail.config.mount_linprocfs:
        return
    except:
      pass

    linproc_path = "compat/linux/proc"
    self._jail_mkdirp(f"{self.path}/root/{linproc_path}")

    try:
      if jail.config.mount_procfs:
        iocage.lib.helpers.exec([
          "mount"
          "-t",
          "linprocfs"
          "linproc"
          f"{self.path}/root/{linproc_path}"
        ])
    except:
      pass

  def _mount_jail_dataset(self, dataset_name):
    self.jail.exec(['zfs', 'mount', dataset_name])

  def _get_pool_name_from_dataset_name(self, dataset_name):
    return dataset_name.split("/", maxsplit=1)[0]

  def _get_pool_from_dataset_name(self, dataset_name):
    target_pool_name = self._get_pool_name_from_dataset_name(dataset_name)
    for zpool in list(self.zfs.pools):
      if zpool.name == target_pool_name:
        return zpool
    raise Exception(f"zpool {target_pool_name} does not exist")

  def _unmount_local(self, dataset):
    if dataset.mountpoint:
      dataset.unmount()

  def _jail_mkdirp(self, directory, permissions=0o775, user="root", group="wheel"):
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    folder = f"{self.jail.path}/{directory}"
    if not os.path.isdir(folder):
      os.mkdirs(folder, permissions)
      os.chown(folder, uid, gid, follow_symlinks=False)

  def _set_fsopts(self, fsopts):
    self.fsopts = fsopts

    default_fsopts = {
      "compression": "lz4"
    }

    for key in default_fsopts:
      try:
        self.fsopts[key]
      except:
        self.fsopts[key] = default_fsopts[key]
