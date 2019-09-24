from iocage_lib.resource import Resource
from iocage_lib.zfs import (
    ZFSException, create_dataset, get_dependents, destroy_zfs_resource,
    umount_dataset, mount_dataset, get_dataset_from_mountpoint,
    rename_dataset,
)

import iocage_lib.snapshot as snapshot

import contextlib
import os


class Dataset(Resource):

    zfs_resource = 'zfs'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if os.path.exists(self.name):
            # Probably absolute path has been provided, in this case
            # we try to find the name of the dataset, if we don't succeed,
            # we keep the value as it is
            with contextlib.suppress(ZFSException):
                self.resource_name = self.name = get_dataset_from_mountpoint(
                    self.name
                )

    def create(self, data):
        return create_dataset({'name': self.resource_name, **data})

    def rename(self, new_name, options=None):
        result = rename_dataset(self.name, new_name, options)
        if result:
            self.name = self.resource_name = new_name
        return result

    def create_snapshot(self, snap_name, options=None):
        snap = snapshot.Snapshot(f'{self.resource_name}@{snap_name}')
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
        return snapshot.SnapshotListableResource(
            resource_name=self.resource_name, recursive=True
        )

    @property
    def exists(self):
        return os.path.exists(self.path)

    def get_dependents(self, depth=1):
        for d in get_dependents(self.resource_name, depth):
            yield Dataset(d)

    def destroy(self, recursive=False, force=False):
        return destroy_zfs_resource(self.resource_name, recursive, force)

    def mount(self):
        return mount_dataset(self.resource_name)

    def umount(self):
        return umount_dataset(self.resource_name)
