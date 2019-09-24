from iocage_lib.resource import Resource, ListableResource
from iocage_lib.zfs import (
    list_snapshots, destroy_zfs_resource, iocage_activated_dataset,
    rollback_snapshot, create_snapshot, clone_snapshot
)

import iocage_lib.dataset as dataset

import os


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
        return dataset.Dataset(self.resource_name.split('@', 1)[0])

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
        iocage_dataset = dataset.Dataset(iocage_activated_dataset())
        if iocage_dataset.exists:

            for snap in list_snapshots(
                resource=os.path.join(iocage_dataset.path, 'releases'),
                recursive=True,
            ):
                yield self.resource(snap)
