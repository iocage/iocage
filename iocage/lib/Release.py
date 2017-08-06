import helpers

import os
import tarfile
import hashlib
import libzfs
import urllib.request
import shutil
import uuid
import datetime
from urllib.parse import urlparse

import Jail


class Release:

    def __init__(self, name=None,
                 dataset=None,
                 host=None,
                 zfs=None,
                 logger=None,
                 check_hashes=True,
                 auto_fetch_updates=True,
                 auto_update=True):

        helpers.init_logger(self, logger)
        helpers.init_zfs(self, zfs)
        helpers.init_host(self, host)

        self.name = name
        self._hashes = None
        self._dataset = None
        self._root_dataset = None
        self.dataset = dataset
        self.check_hashes = check_hashes is True
        self.auto_fetch_updates = auto_fetch_updates is True
        self.auto_update = auto_update is True

        self._assets = ["base"]
        if self.host.distribution.name != "HardenedBSD":
            self._assets.append("lib32")

    @property
    def dataset(self):
        if self._dataset is None:
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
    def root_dataset(self):
        if self._root_dataset is None:
            try:
                self._root_dataset = self.zfs.get_dataset(self.root_dataset_name)
            except:
                self.host.datasets.releases.pool.create(self.root_dataset_name, {}, create_ancestors=True)
                self._root_dataset = self.zfs.get_dataset(self.root_dataset_name)
                self._root_dataset.mount()

        return self._root_dataset

    @property
    def dataset_name(self):
        return f"{self.host.datasets.releases.name}/{self.name}"

    @property
    def root_dataset_name(self):
        return f"{self.host.datasets.releases.name}/{self.name}/root"

    @property
    def releases_folder(self):
        return self.host.datasets.releases.mountpoint

    @property
    def base_dataset(self):
        # base datasets are created from releases. required to start
        # zfs-basejails
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
            if self.root_dataset.mountpoint:
                return self.root_dataset.mountpoint
        except:
            pass

        return f"{self.releases_folder}/{self.name}/root"

    @property
    def assets(self):
        return self._assets

    @assets.setter
    def assets(self, value):
        value = [value] if isinstance(value, str) else value
        self._assets = map(
            lambda x: x if not x.endswith(".txz") else x[:-4],
            value
        )

    @property
    def mirror_url(self):
        try:
            if self._mirror_url:
                return self._mirror_url
        except:
            pass
        return self.host.distribution.mirror_url

    @mirror_url.setter
    def mirror_url(self, value):
        url = urlparse(value)
        if url.scheme not in self._supported_url_schemes:
            raise Exception(f"Invalid URL scheme '{url.scheme}'")
        self._mirror_url = url.geturl()

    @property
    def remote_url(self):
        return f"{self.mirror_url}/{self.name}"

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
        if not os.path.isdir(self.root_dir):
            return False

        root_dir_index = os.listdir(self.root_dir)

        for expected_directory in ["dev", "var", "etc"]:
            if expected_directory not in root_dir_index:
                return False

        return True

    @property
    def zfs_pool(self):
        try:
            return self.host.datasets.releases.pool
        except:
            pass

        try:
            return self.root_dataset.pool
        except:
            pass

        raise Exception(
            "Cannot find the ZFS pool without knowing"
            "the dataset or release_dataset"
        )

    @property
    def hashes(self):
        if not self._hashes:
            if not os.path.isfile(self.__get_hashfile_location()):
                self.logger.spam("hashes have not yet been downloaded.")
                self._fetch_hashes()
            self._hashes = self.read_hashes()

        return self._hashes

    @property
    def _supported_url_schemes(self):
        return ["https", "http", "ftp"]

    @property
    def release_updates_dir(self):
        return f"{self.dataset.mountpoint}/updates"

    @property
    def _is_root_dir_empty(self):
        root_dir_exists = os.path.isdir(self.root_dir)
        return not (root_dir_exists and os.listdir(self.root_dir) != [])

    def fetch(self, update=None, fetch_updates=None):

        release_changed = False

        if self._is_root_dir_empty:
            self._require_empty_root_dir()
            self._create_dataset()
            self._ensure_dataset_mounted()
            self._fetch_assets()
            self._extract_assets()
            release_changed = True
        else:
            self.logger.warn(
                "Release was already downloaded. Skipping download."
            )

        fetch_updates_on = self.auto_fetch_updates and fetch_updates is not False
        if fetch_updates_on or fetch_updates:
            self.fetch_updates()

        auto_update_on = self.auto_update and update is not False
        if auto_update_on or update:
            release_changed = self.update()

        if release_changed:
            self._update_zfs_base()

        self._cleanup()

    def fetch_updates(self):

        release_updates_dir = self.release_updates_dir
        release_update_download_dir = f"{release_updates_dir}"

        if os.path.isdir(release_update_download_dir):
            self.logger.verbose(
                f"Deleting existing updates in {release_update_download_dir}"
            )
            shutil.rmtree(release_update_download_dir)

        os.makedirs(release_update_download_dir)

        files = {
            "freebsd-update.sh": "usr.sbin/freebsd-update/freebsd-update.sh",
            "freebsd-update.conf": "etc/freebsd-update.conf",
        }

        for key in files.keys():

            remote_path = files[key]
            url = self.host.distribution.get_release_trunk_file_url(
                release=self,
                filename=remote_path
            )

            local_path = f"{release_updates_dir}/{key}"

            if os.path.isfile(local_path):
                os.remove(local_path)

            self.logger.verbose(f"Downloading {url}")
            urllib.request.urlretrieve(url, local_path)

            if key == "freebsd-update.sh":
                os.chmod(local_path, 0o755)
            elif key == "freebsd-update.conf":
                with open(local_path, "r+") as f:
                    content = f.read()
                    f.seek(0)
                    f.write(content.replace("Components src", "Components"))
                    f.truncate()
                    f.close()
                os.chmod(local_path, 0o644)

            self.logger.debug(
                f"Update-asset {key} for release '{self.name}'"
                f" saved to {local_path}"
            )

        self.logger.verbose(f"Fetching updates for release '{self.name}'")
        helpers.exec([
            f"{self.release_updates_dir}/freebsd-update.sh",
            "-d",
            release_update_download_dir,
            "-f",
            f"{self.release_updates_dir}/freebsd-update.conf",
            "--not-running-from-cron",
            "fetch"
        ], logger=self.logger)

    def update(self):
        dataset = self.dataset
        snapshot_name = self._append_datetime(f"{dataset.name}@pre-update")

        # create snapshot before the changes
        dataset.snapshot(snapshot_name, recursive=True)

        jail = Jail.Jail({
            "uuid": uuid.uuid4(),
            "basejail": False,
            "allow_mount_nullfs": "1",
            "release": self.name
        },
            logger=self.logger,
            zfs=self.zfs,
            host=self.host
        )

        jail.set_dataset_name(self.dataset_name)

        local_update_mountpoint = f"{self.root_dir}/var/db/freebsd-update"
        if not os.path.isdir(local_update_mountpoint):
            self.logger.spam(
                "Creating mountpoint {local_update_mountpoint}"
            )
            os.makedirs(local_update_mountpoint)

        try:

            jail.config.fstab.add(
                self.release_updates_dir,
                local_update_mountpoint,
                "nullfs",
                "rw"
            )
            jail.config.fstab.save()

            jail.start()

            child, stdout, stderr = jail.exec([
                "/var/db/freebsd-update/freebsd-update.sh",
                "-d",
                "/var/db/freebsd-update",
                "-f",
                "/var/db/freebsd-update/freebsd-update.conf",
                "install"
            ], ignore_error=True)

            if child.returncode == 1:
                if "No updates are available to install." in stdout:
                    self.logger.debug("Already up to date")
                    changed = True
                else:
                    msg = ("Release '{self.name}' failed"
                           " running freebsd-update.sh")
                    raise Exception(msg)
            else:
                self.logger.debug(f"Update of release '{self.name}' finished")
                changed = True

            jail.stop()

            self.logger.verbose(f"Release '{self.name}' updated")
            return changed

        except:
            self.logger.verbose(
                "There was an error updating the Jail - reverting the changes"
            )
            jail.force_stop()
            self.zfs.get_snapshot(snapshot_name).rollback(force=True)
            raise

    def _append_datetime(self, text):
        now = datetime.datetime.utcnow()
        text += now.strftime("%Y%m%d%H%I%S.%f")
        return text

    def _basejail_datasets_already_exists(self, release_name):
        base_dataset = self.host.datasets.base
        for dataset in base_dataset.children:
            if dataset.name == f"{base_dataset.name}/release_name":
                return True
        return False

    def _create_dataset(self, name=None):

        if name is None:
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

    def _fetch_hashes(self):
        url = f"{self.remote_url}/{self.host.distribution.hash_file}"
        path = self.__get_hashfile_location()
        self.logger.verbose(f"Downloading hashes from {url}")
        urllib.request.urlretrieve(url, path)
        self.logger.debug(f"Hashes downloaded to {path}")

    def _fetch_assets(self):
        for asset in self.assets:
            url = f"{self.remote_url}/{asset}.txz"
            path = self._get_asset_location(asset)

            if os.path.isfile(path):
                self.logger.verbose(f"{path} already exists - skipping.")
                return
            else:
                self.logger.debug(f"Starting download of {url}")
                urllib.request.urlretrieve(url, path)
                self.logger.verbose(f"{url} was saved to {path}")

    def _require_empty_root_dir(self):
        if not self._is_root_dir_empty:
            msg = f"The directory '{self.root_dir}' is not empty"
            self.logger.error(msg)
            raise Exception(msg)

    def read_hashes(self):
        # yes, this can read HardenedBSD and FreeBSD hash files
        path = self.__get_hashfile_location()
        hashes = {}
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
                    hashes[asset] = fingerprint
        count = len(hashes)
        self.logger.spam(f"{count} hashes read from {path}")
        return hashes

    def __get_hashfile_location(self):
        hash_file = self.host.distribution.hash_file
        return f"{self.download_directory}/{hash_file}"

    def _get_asset_location(self, asset_name):
        return f"{self.download_directory}/{asset_name}.txz"

    def _extract_assets(self):

        for asset in self.assets:

            if self.check_hashes:
                self._check_asset_hash(asset)

            with tarfile.open(self._get_asset_location(asset)) as f:

                self.logger.verbose(f"Verifying file structure in {asset}")
                self._check_tar_files(f.getmembers())

                self.logger.debug(f"Extracting {asset}")
                f.extractall(self.root_dir)
                self.logger.verbose(
                    f"Asset {asset} was extracted to {self.root_dir}"
                )

    def _update_name_from_dataset(self):
        if self.dataset:
            self.name = self.dataset.name.split("/")[-2:-1]

    def _update_zfs_base(self):

        try:
            self.host.datasets.base.pool.create(
                self.base_dataset_name, {}, create_ancestors=True)
            self.base_dataset.mount()
        except:
            pass

        base_dataset = self.base_dataset
        pool = self.host.datasets.base.pool

        for folder in helpers.get_basedir_list():
            try:
                pool.create(
                    f"{base_dataset.name}/{folder}",
                    {},
                    create_ancestors=True
                )
                self.zfs.get_dataset(f"{base_dataset.name}/{folder}").mount()
            except:
                # dataset was already existing
                pass

            src = self.root_dataset.mountpoint
            dst = f"{base_dataset.mountpoint}/{folder}"

            self.logger.verbose(f"Copying {folder} from {src} to {dst}")
            self._copytree(src, dst)

        self.logger.debug(f"Updated release base datasets for {self.name}")

    def _copytree(self, src_path, dst_path, delete=False):

        src_dir = set(os.listdir(src_path))
        dst_dir = set(os.listdir(dst_path))

        if delete is True:
            for item in dst_dir - src_dir:
                self._rmtree("f{dst_dir}/{item}")

        for item in os.listdir(src_path):
            src = os.path.join(src_path, item)
            dst = os.path.join(dst_path, item)
            if os.path.islink(src) or os.path.isfile(src):
                self._copyfile(src, dst)
            else:
                if not os.path.isdir(dst):
                    src_stat = os.stat(src)
                    os.makedirs(dst, src_stat.st_mode)
                self._copytree(src, dst)

    def _copyfile(self, src_path, dst_path):

        dst_flags = None

        if os.path.islink(dst_path):
            os.unlink(dst_path)
        elif os.path.isfile(dst_path) or os.path.isdir(dst_path):
            dst_stat = os.stat(dst_path)
            dst_flags = dst_stat.st_flags
            self._rmtree(dst_path)

        if os.path.islink(src_path):
            linkto = os.readlink(src_path)
            os.symlink(linkto, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
            if dst_flags is not None:
                os.chflags(dst_path, dst_flags)

    def _rmtree(self, path):
        if os.path.islink(path):
            os.unlink(path)
            return
        elif os.path.isdir(path):
            for item in os.listdir(path):
                self._rmtree(f"{path}/{item}")
            os.chflags(path, 2048)
            os.rmdir(path)
        else:
            os.chflags(path, 2048)
            os.remove(path)

    def _cleanup(self):
        for asset in self.assets:
            asset_location = self._get_asset_location(asset)
            if os.path.isfile(asset_location):
                os.remove(asset_location)

    def _check_asset_hash(self, asset_name):
        local_file_hash = self._read_asset_hash(asset_name)
        expected_hash = self.hashes[asset_name]

        has_valid_hash = local_file_hash == expected_hash
        if not has_valid_hash:
            self.logger.warn(
                f"Asset {asset_name}.txz has an invalid signature"
                f"(was '{local_file_hash}' but expected '{expected_hash}')"
            )
            raise Exception("Invalid Signature")

        self.logger.spam(
            f"Asset {asset_name}.txz has a valid signature ({expected_hash})"
        )

    def _read_asset_hash(self, asset_name):
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
                msg = "Names in txz files must be relative and begin with './'"
                self.logger.error(msg)
                raise Exception(msg)
            if ".." in i.name:
                msg = "Names in txz files must not contain '..'"
                self.logger.error(msg)
                raise Exception(msg)
