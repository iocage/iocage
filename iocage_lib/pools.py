from iocage_lib.ioc_exceptions import PoolNotActivated
from iocage_lib.resource import Resource, ListableResource
from iocage_lib.zfs import list_pools, IOCAGE_POOL_PROP, pool_health

import iocage_lib.dataset as dataset

Dataset = dataset.Dataset


class Pool(Resource):

    zfs_resource = 'zpool'

    @property
    def active(self):
        return Dataset(self.name).properties[IOCAGE_POOL_PROP] == 'yes'

    @property
    def health(self):
        return pool_health(self.name)

    def activate_pool(self):
        if self.health != 'ONLINE':
            raise PoolNotActivated(
                f'Please check pool status, it should be ONLINE'
            )

        Dataset(self.name).set_property(IOCAGE_POOL_PROP, 'yes')
        self.comment_check()

    def comment_check(self):
        if self.properties.get('comment') == 'iocage':
            self.set_property('comment', '-')
        else:
            ds = Dataset(self.name)
            if ds.properties.get('comment') == 'iocage':
                ds.set_property('comment', '-')

    def deactivate_pool(self):
        Dataset(self.name).set_property(IOCAGE_POOL_PROP, 'no')
        self.comment_check()

    def __eq__(self, other):
        return other.name == self.name

    def create_dataset(self, data):
        ds = Dataset(data['name'])
        ds.create(data)
        return ds

    @property
    def path(self):
        return None

    @property
    def exists(self):
        return Dataset(self.name).exists


class PoolListableResource(ListableResource):

    resource = Pool

    def __iter__(self):
        for p in list_pools():
            yield self.resource(p)
