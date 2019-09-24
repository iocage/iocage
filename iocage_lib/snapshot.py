from iocage_lib.resource import Resource, ListableResource
from iocage_lib.zfs import (
    list_snapshots, destroy_zfs_resource, iocage_activated_dataset
)

import iocage_lib.dataset as dataset

import pathlib


class Snapshot(Resource):

    def __eq__(self, other):
        return self.name == other.name

    @property
    def dataset(self):
        return dataset.Dataset(self.name.split('@', 1)[0])

    @property
    def exists(self):
        return bool(list_snapshots(raise_error=False, resource=self.name))

    @property
    def path(self):
        return None

    def destroy(self, recursive=True, force=True):
        return destroy_zfs_resource(self.name, recursive, force)


class SnapshotListableResource(ListableResource):

    resource = Snapshot

    def __init__(self, *args, **kwargs):
        self.resource = kwargs.get('resource', False)
        self.recursive = kwargs.get('recursive', False)
        super().__init__(*args, **kwargs)

    def __iter__(self):
        for snap in list_snapshots(
            resource=self.resource, recursive=self.recursive
        ):
            yield self.resource(snap)

    @property
    def release_snapshots(self):
        # Returns all jail snapshots on each RELEASE dataset
        iocage_dataset = dataset.Dataset(iocage_activated_dataset())
        if iocage_dataset.exists:
            rel_dir = pathlib.Path(f'{iocage_dataset.path}/releases')

            # Quicker than asking zfs and parsing
            for snap in rel_dir.glob('**/root/.zfs/snapshot/*'):
                yield Snapshot(snap.name)
