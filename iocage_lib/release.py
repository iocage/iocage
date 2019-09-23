import os
import re
import requests

from iocage_lib.dataset import Dataset
from iocage_lib.resource import  IocageListableResource
from iocage_lib.ioc_fetch import IOCFetch
from iocage_lib.ioc_common import check_release_newer


class Release(Dataset):

    @property
    def path(self):
        return os.path.join(self.iocage_path(), 'releases', self.name)


class ListableReleases(IocageListableResource):

    resource = Release
    path = 'releases'

    def __init__(self, remote=False, eol_check=True):
        # We should abstract distribution and have eol checks live there in
        # the future probably plus release should be able to tell if it's eol
        # or not. Also perhaps we should think of a filter
        # interface.
        super().__init__()
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
                ) and not check_release_newer(r, raise_error=False),
                re.findall(
                    r'href="(\d.*RELEASE)/"', req.content.decode('utf-8')
                )
            ):
                yield self.resource(release)
        else:
            for r in super().__iter__():
                yield r
