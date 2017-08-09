import iocage.lib.Release
import iocage.lib.helpers

import os
import platform
import re
import urllib.request


class Distribution:

    release_name_blacklist = [
        "",
        ".",
        "..",
        "ISO-IMAGES"
    ]

    mirror_link_pattern = r"a href=\"([A-z0-9\-_\.]+)/\""

    def __init__(self, host, zfs=None, logger=None):
        iocage.lib.helpers.init_logger(self, logger)
        iocage.lib.helpers.init_zfs(self, zfs)
        self.host = host
        self.available_releases = None

    @property
    def name(self):
        if os.uname()[2].endswith("-HBSD"):
            return "HardenedBSD"
        else:
            return platform.system()

    @property
    def mirror_url(self):

        distribution = self.name
        processor = self.host.processor

        if distribution == "FreeBSD":
            release_path = f"/pub/FreeBSD/releases/{processor}/{processor}"
            return f"http://ftp.freebsd.org{release_path}"
        elif distribution == "HardenedBSD":
            return f"http://jenkins.hardenedbsd.org/builds"
        else:
            raise Exception(f"Unknown Distribution '{distribution}'")

    @property
    def hash_file(self):
        if self.name == "FreeBSD":
            return "MANIFEST"
        elif self.name == "HardenedBSD":
            return "CHECKSUMS.SHA256"

    def fetch_releases(self):

        resource = urllib.request.urlopen(self.mirror_url)
        charset = resource.headers.get_content_charset()
        response = resource.read().decode(charset if charset else "UTF-8")

        available_releases = list(map(lambda x: iocage.lib.Release.Release(
            name=x,
            host=self.host,
            zfs=self.zfs,
            logger=self.logger
        ),
            self._parse_links(response)
        ))

        available_releases = sorted(
            available_releases,
            key=lambda x: float(x.name.partition("-")[0])
        )

        self.available_releases = available_releases
        return available_releases

    def get_release_trunk_file_url(self, release, filename):

        if self.host.distribution.name == "HardenedBSD":
            # ToDo: implement HardenedBSD release updates
            raise Exception(
                "Updates of HardenedBSD releases not supported yet"
            )
        elif self.host.distribution.name == "FreeBSD":

            if release.name == "11.0-RELEASE":
                release_name = "11.0.1"
            else:
                fragments = release.name.split("-", maxsplit=1)
                release_name = f"{fragments[0]}.0"

            base_url = "https://svnweb.freebsd.org/base/release"
            return f"{base_url}/{release_name}/{filename}?view=co"

    @property
    def releases(self):
        if not self.available_releases:
            self.fetch_releases()
        return self.available_releases

    def _parse_links(self, text):
        blacklisted_releases = Distribution.release_name_blacklist
        matches = filter(lambda y: y not in blacklisted_releases,
                         map(lambda z: z.strip("\"/"),
                             re.findall(
                                 Distribution.mirror_link_pattern,
                                 text,
                                 re.MULTILINE)
                             )
                         )

        if self.name == "HardenedBSD":
            matches = filter(
                lambda x: x.endswith(f"-{self.host.processor}-LATEST")
            )

        return matches
