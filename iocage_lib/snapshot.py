from iocage_lib.resource import Resource, ListableResource
from iocage_lib.zfs import list_snapshots


class Snapshot(Resource):

    def __eq__(self, other):
        return self.name == other.name

    @property
    def exists(self):
        return bool(list_snapshots(raise_error=False, snapshot=self.name))

    @property
    def path(self):
        return None


class SnapshotListableResource(ListableResource):

    resource = Snapshot

    def __iter__(self):
        for snap in list_snapshots():
            yield self.resource(snap)
