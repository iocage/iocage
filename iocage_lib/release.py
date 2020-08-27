import os
import re
import requests

import iocage_lib.dataset as dataset

from iocage_lib.cache import cache
from iocage_lib.resource import IocageListableResource
from iocage_lib.ioc_fetch import IOCFetch
from iocage_lib.ioc_common import check_release_newer


class Release(dataset.Dataset):

    def __init__(self, name, *args, **kwargs):
        if '/' not in name and cache.iocage_activated_dataset:
            name = os.path.join(cache.iocage_activated_dataset, 'releases', name)
        super().__init__(name, *args, **kwargs)
        if self.resource_name:
            self.name = self.resource_name.rsplit('/', 1)[-1]

    def __repr__(self):
        return str(self.name)

    def __str__(self):
        return str(self.name)


class ListableReleases(IocageListableResource):

    resource = Release

    def __init__(self, remote=False, eol_check=True):
        # We should abstract distribution and have eol checks live there in
        # the future probably plus release should be able to tell if it's eol
        # or not. Also perhaps we should think of a filter
        # interface.
        super().__init__()
        if self.dataset_path:
            self.dataset_path = os.path.join(self.dataset_path, 'releases')
        self.remote = remote
        self.eol_check = eol_check
        self.eol_list = []
        if eol_check and remote:
            # TODO: Please let's not use this in the future and look at
            # comments above
            self.eol_list = IOCFetch.__fetch_eol_check__()

    def __iter__(self):
        if self.remote:
            # TODO: Please abstract this in the future
            req = requests.get(
                'https://download.freebsd.org/ftp/'
                f'releases/{os.uname().machine}/', timeout=10
            )

            assert req.status_code == 200

            for release in filter(
                lambda r: (
                    r if not self.eol_check else r not in self.eol_list
                ) and not check_release_newer(
                    r, raise_error=False, major_only=True
                ),
                re.findall(
                    r'href="(\d.*RELEASE)/"', req.content.decode('utf-8')
                )
            ):
                yield self.resource(release)
        else:
            for r in super().__iter__():
                yield r
