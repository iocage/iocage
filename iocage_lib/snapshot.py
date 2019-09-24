from iocage_lib.resource import Resource, ListableResource
from iocage_lib.zfs import (
    list_snapshots, destroy_zfs_resource, iocage_activated_dataset
)

import iocage_lib.dataset as dataset

import os


class Snapshot(Resource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if '@' in self.resource_name:
            self.name = self.resource_name.split('@', 1)[-1]

    def __eq__(self, other):
        return self.resource_name == other.resource_name

    @property
    def dataset(self):
        return dataset.Dataset(self.resource_name.split('@', 1)[0])

    @property
    def exists(self):
        return bool(list(list_snapshots(
            raise_error=False, resource=self.resource_name)
        ))

    @property
    def path(self):
        return None

    def destroy(self, recursive=True, force=True):
        return destroy_zfs_resource(self.resource_name, recursive, force)


class SnapshotListableResource(ListableResource):

    resource = Snapshot

    def __init__(self, *args, **kwargs):
        self.resource_name = kwargs.get('resource', False)
        self.recursive = kwargs.get('recursive', False)
        super().__init__(*args, **kwargs)

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
