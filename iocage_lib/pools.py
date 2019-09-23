from iocage_lib.ioc_exceptions import PoolNotActivated
from iocage_lib.resource import ZFSResource, ListableResource
from iocage_lib.zfs import list_pools, IOCAGE_POOL_PROP, pool_health


class Pool(ZFSResource):

    @property
    def active(self):
        return self.properties[IOCAGE_POOL_PROP] == 'yes'

    @property
    def health(self):
        return pool_health(self.name)

    def activate_pool(self):
        if self.health != 'ONLINE':
            raise PoolNotActivated(
                f'Please check pool status, it should be ONLINE'
            )

        self.set_property(IOCAGE_POOL_PROP, 'yes')
        self.comment_check()

    def comment_check(self):
        if self.properties['comment'] == 'iocage':
            self.set_property('comment', '-')

    def deactivate_pool(self):
        self.set_property(IOCAGE_POOL_PROP, 'no')
        self.comment_check()


class PoolListableResource(ListableResource):

    resource = Pool

    def __iter__(self):
        for p in list_pools():
            yield self.resource(p)
