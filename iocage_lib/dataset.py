from iocage_lib.cache import cache
from iocage_lib.resource import Resource, ListableResource
from iocage_lib.zfs import (
    ZFSException, create_dataset, get_dependents, destroy_zfs_resource,
    umount_dataset, mount_dataset, get_dataset_from_mountpoint,
    rename_dataset, dataset_exists, promote_dataset, list_snapshots,
    iocage_activated_dataset, rollback_snapshot, create_snapshot,
    clone_snapshot,
)

import contextlib
import os

from copy import deepcopy


class Dataset(Resource):

    zfs_resource = 'zfs'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if os.path.exists(self.name):
            # Probably absolute path has been provided, in this case
            # we try to find the name of the dataset, if we don't succeed,
            # we keep the value as it is
            with contextlib.suppress(StopIteration, ZFSException):
                if not self.cache:
                    self.resource_name = self.name = \
                        get_dataset_from_mountpoint(self.name)
                else:
                    self.resource_name = self.name = next((
                        n for n, v in cache.datasets.items()
                        if v.get('mountpoint') == self.name
                    ))

        if self.cache:
            self._properties = deepcopy(cache.datasets.get(self.resource_name))

    def create(self, data):
        cache.reset()
        return create_dataset({'name': self.resource_name, **data})

    def rename(self, new_name, options=None):
        result = rename_dataset(self.name, new_name, options)
        if result:
            self.name = self.resource_name = new_name
            cache.reset()
        return result

    def create_snapshot(self, snap_name, options=None):
        snap = Snapshot(f'{self.resource_name}@{snap_name}')
        snap.create_snapshot(options)
        return snap

    @property
    def path(self):
        try:
            return self.properties['mountpoint']
        except ZFSException:
            # Unable to find zfs resource
            return ''

    def __eq__(self, other):
        return other.path == self.path

    def snapshots_recursive(self):
        return SnapshotListableResource(
            resource_name=self.resource_name, recursive=True
        )

    @property
    def exists(self):
        return dataset_exists(self.resource_name) if not self.cache else \
            self.resource_name in cache.datasets

    @property
    def mounted(self):
        return self.properties['mounted'] == 'yes'

    def get_dependents(self, depth=1, ds_cache=True):
        gd = cache.dependents if ds_cache else get_dependents
        for d in gd(self.resource_name, depth):
            ds = Dataset(d, cache=ds_cache)
            if ds.locked:
                continue
            yield ds

    @property
    def locked(self):
        return not self.mounted or (
            self.properties.get('encryption', 'off') != 'off'
            and self.properties.get('keystatus', 'available') != 'available'
        )

    def destroy(self, recursive=False, force=False):
        cache.reset()
        return destroy_zfs_resource(self.resource_name, recursive, force)

    def mount(self):
        cache.reset()
        return mount_dataset(self.resource_name)

    def promote(self):
        return promote_dataset(self.resource_name)

    def umount(self, force=True):
        cache.reset()
        return umount_dataset(self.resource_name, force)


class Snapshot(Resource):

    zfs_resource = 'zfs'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if '@' in self.resource_name:
            self.name = self.resource_name.split('@', 1)[-1]

    def __eq__(self, other):
        return self.resource_name == other.resource_name

    @property
    def dataset(self):
        return Dataset(self.resource_name.split('@', 1)[0])

    def create_snapshot(self, options=None):
        return create_snapshot(self.resource_name, options)

    @property
    def exists(self):
        return bool(list(list_snapshots(
            raise_error=False, resource=self.resource_name)
        ))

    def rollback(self, options=None):
        return rollback_snapshot(self.resource_name, options)

    def clone(self, dataset):
        return clone_snapshot(self.resource_name, dataset)

    @property
    def path(self):
        return None

    def destroy(self, recursive=True, force=True):
        return destroy_zfs_resource(self.resource_name, recursive, force)


class SnapshotListableResource(ListableResource):

    resource = Snapshot

    def __init__(self, *args, **kwargs):
        self.resource_name = kwargs.pop('resource_name', False)
        self.recursive = kwargs.pop('recursive', False)

    def __iter__(self):
        for snap in list_snapshots(
            resource=self.resource_name, recursive=self.recursive
        ):
            yield self.resource(snap)

    @property
    def release_snapshots(self):
        # Returns all jail snapshots on each RELEASE dataset
        releases_dataset = Dataset(
            os.path.join(iocage_activated_dataset(), 'releases')
        )
        if releases_dataset.exists:

            for snap in list_snapshots(
                resource=releases_dataset.name,
                recursive=True,
            ):
                yield self.resource(snap)
