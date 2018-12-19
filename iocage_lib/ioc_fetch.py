# Copyright (c) 2014-2018, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""iocage fetch module."""
import hashlib
import logging
import os
import shutil
import subprocess as su
import tarfile
import tempfile
import time
import urllib.request

import requests
import requests.auth
import requests.packages.urllib3.exceptions

import iocage_lib.ioc_common
import iocage_lib.ioc_destroy
import iocage_lib.ioc_exec
import iocage_lib.ioc_json
import iocage_lib.ioc_start
import libzfs


class IOCFetch(iocage_lib.ioc_json.IOCZFS):

    """Fetch a RELEASE for use as a jail base."""

    def __init__(self,
                 release,
                 server="download.freebsd.org",
                 user="anonymous",
                 password="anonymous@",
                 auth=None,
                 root_dir=None,
                 http=True,
                 _file=False,
                 verify=True,
                 hardened=False,
                 update=True,
                 eol=True,
                 files=('MANIFEST', 'base.txz', 'lib32.txz', 'src.txz'),
                 silent=False,
                 callback=None):
        super().__init__()
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.server = server
        self.user = user
        self.password = password
        self.auth = auth

        if release and (not _file and server == 'download.freebsd.org'):
            self.release = release.upper()
        else:
            self.release = release

        self.root_dir = root_dir
        self.arch = os.uname()[4]
        self.http = http
        self._file = _file
        self.verify = verify
        self.hardened = hardened
        self.files = files
        self.files_left = list(files)
        self.update = update
        self.eol = eol
        self.silent = silent
        self.callback = callback
        self.zpool = self.zfs.get(self.pool)

        if hardened:
            if release:
                self.release = f"{self.release[:2]}-stable".upper()
            else:
                self.release = release

        if not verify:
            # The user likely knows this already.
            requests.packages.urllib3.disable_warnings(
                requests.packages.urllib3.exceptions.InsecureRequestWarning)

    @staticmethod
    def __fetch_eol_check__():
        """Scrapes the FreeBSD website and returns a list of EOL RELEASES"""
        logging.getLogger("requests").setLevel(logging.WARNING)
        _eol = "https://www.freebsd.org/security/unsupported.html"
        req = requests.get(_eol)
        status = req.status_code == requests.codes.ok
        eol_releases = []

        if not status:
            req.raise_for_status()

        for eol in req.content.decode("iso-8859-1").split():
            eol = eol.strip("href=").strip("/").split(">")
            # We want a dynamic EOL
            try:
                if "-RELEASE" in eol[1]:
                    eol = eol[1].strip('</td')

                    if eol not in eol_releases:
                        eol_releases.append(eol)
            except IndexError:
                pass

        return eol_releases

    def __fetch_validate_release__(self, releases):
        """
        Checks if the user supplied an index number and returns the
        RELEASE. If they gave us a full RELEASE, we make sure that exists in
        the list at all.
        """

        if self.release.lower() == "exit" or self.release.lower() == "q":
            exit()

        if len(self.release) > 2:
            # Quick list validation
            try:
                releases.index(self.release)
            except ValueError:
                # Time to print the list again
                for r in releases:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"[{releases.index(r)}] {r}"
                        },
                        _callback=self.callback,
                        silent=self.silent)
                host_release = iocage_lib.ioc_common.get_host_release()
                self.release = input("\nType the number of the desired"
                                     " RELEASE\nPress [Enter] to fetch "
                                     f"the default selection: ({host_release})"
                                     "\nType EXIT to quit: ")
                self.release = self.__fetch_validate_release__(releases)

            return self.release

        try:
            self.release = releases[int(self.release)]
            iocage_lib.ioc_common.check_release_newer(
                self.release, self.callback, self.silent)
        except IndexError:
            # Time to print the list again

            for r in releases:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": f"[{releases.index(r)}] {r}"
                    },
                    _callback=self.callback,
                    silent=self.silent)
            host_release = iocage_lib.ioc_common.get_host_release()
            self.release = input("\nType the number of the desired"
                                 " RELEASE\nPress [Enter] to fetch "
                                 f"the default selection: ({host_release})"
                                 "\nType EXIT to quit: ")
            self.release = self.__fetch_validate_release__(releases)
        except ValueError:
            # We want to use their host as RELEASE, but it may
            # not be on the mirrors anymore.
            try:
                if self.release == "":
                    self.release = iocage_lib.ioc_common.get_host_release()

                if "-STABLE" in self.release:
                    # Custom HardenedBSD server
                    self.hardened = True

                    return self.release

                releases.index(self.release)
            except ValueError:
                # Time to print the list again

                for r in releases:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"[{releases.index(r)}] {r}"
                        },
                        _callback=self.callback,
                        silent=self.silent)
                host_release = iocage_lib.ioc_common.get_host_release()
                self.release = input("\nType the number of the desired"
                                     " RELEASE\nPress [Enter] to fetch "
                                     f"the default selection: ({host_release})"
                                     "\nType EXIT to quit: ")
                self.release = self.__fetch_validate_release__(releases)

        return self.release

    def fetch_release(self, _list=False):
        """Small wrapper to choose the right fetch."""

        if self.http and not self._file:
            if self.eol and self.verify:
                eol = self.__fetch_eol_check__()
            else:
                eol = []

            rel = self.fetch_http_release(eol, _list=_list)

            if _list:
                return rel
        elif self._file:
            # Format for file directory should be: root-dir/RELEASE/*.txz

            if not self.root_dir:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": "Please supply --root-dir or -d."
                    },
                    _callback=self.callback,
                    silent=self.silent)

            if self.release is None:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": "Please supply a RELEASE!"
                    },
                    _callback=self.callback,
                    silent=self.silent)

            try:
                os.chdir(f"{self.root_dir}/{self.release}")
            except OSError as err:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": err
                    },
                    _callback=self.callback,
                    silent=self.silent)

            dataset = f"{self.iocroot}/download/{self.release}"
            pool_dataset = f"{self.pool}/iocage/download/{self.release}"

            if os.path.isdir(dataset):
                pass
            else:
                self.zpool.create(pool_dataset, {"compression": "lz4"})
                self.zfs.get_dataset(pool_dataset).mount()

            for f in self.files:
                if not os.path.isfile(f):

                    _dataset = self.zfs.get_dataset(pool_dataset)

                    _dataset.umount()
                    _dataset.delete()

                    if f == "MANIFEST":
                        error = f"{f} is a required file!" \
                            f"\nPlease place it in {self.root_dir}/" \
                                f"{self.release}"
                    else:
                        error = f"{f}.txz is a required file!" \
                            f"\nPlease place it in {self.root_dir}/" \
                                f"{self.release}"

                    iocage_lib.ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": error
                        },
                        _callback=self.callback,
                        silent=self.silent)

                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": f"Copying: {f}... "
                    },
                    _callback=self.callback,
                    silent=self.silent)
                shutil.copy(f, dataset)

                if f != "MANIFEST":
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"Extracting: {f}... "
                        },
                        _callback=self.callback,
                        silent=self.silent)
                    self.fetch_extract(f)

    def fetch_http_release(self, eol, _list=False):
        """
        Fetch a user specified RELEASE from FreeBSD's http server or a user
        supplied one. The user can also specify the user, password and
        root-directory containing the release tree that looks like so:
            - XX.X-RELEASE
            - XX.X-RELEASE
            - XX.X-RELEASE
        """

        if self.hardened:
            if self.server == "download.freebsd.org":
                self.server = "http://jenkins.hardenedbsd.org"
                rdir = "builds"

        if self.root_dir is None:
            self.root_dir = f"ftp/releases/{self.arch}"

        if self.auth and "https" not in self.server:
            self.server = "https://" + self.server
        elif "http" not in self.server:
            self.server = "http://" + self.server

        logging.getLogger("requests").setLevel(logging.WARNING)

        if self.hardened:
            if self.auth == "basic":
                req = requests.get(
                    f"{self.server}/{rdir}",
                    auth=(self.user, self.password),
                    verify=self.verify)
            elif self.auth == "digest":
                req = requests.get(
                    f"{self.server}/{rdir}",
                    auth=requests.auth.HTTPDigestAuth(self.user,
                                                      self.password),
                    verify=self.verify)
            else:
                req = requests.get(f"{self.server}/{rdir}")

            releases = []
            status = req.status_code == requests.codes.ok

            if not status:
                req.raise_for_status()

            if not self.release:
                for rel in req.content.split():
                    rel = rel.decode()
                    rel = rel.strip("href=").strip("/").split(">")

                    if "-STABLE" in rel[0]:
                        rel = rel[0].strip('"').strip("/").strip(
                            "HardenedBSD-").rsplit("-")
                        rel = f"{rel[0]}-{rel[1]}"

                        if rel not in releases:
                            releases.append(rel)

                if len(releases) == 0:
                    iocage_lib.ioc_common.logit(
                        {
                            "level":
                            "EXCEPTION",
                            "message":
                            f"""\
    No RELEASEs were found at {self.server}/{self.root_dir}!
    Please ensure the server is correct and the root-dir is
    pointing to a top-level directory with the format:
        - XX.X-RELEASE
        - XX.X-RELEASE
        - XX.X-RELEASE
    """
                        },
                        _callback=self.callback,
                        silent=self.silent)

                releases = iocage_lib.ioc_common.sort_release(
                    releases, fetch_releases=True)

                for r in releases:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"[{releases.index(r)}] {r}"
                        },
                        _callback=self.callback,
                        silent=self.silent)
                host_release = iocage_lib.ioc_common.get_host_release()
                self.release = input("\nType the number of the desired"
                                     " RELEASE\nPress [Enter] to fetch "
                                     f"the default selection: ({host_release})"
                                     "\nType EXIT to quit: ")
                self.release = self.__fetch_validate_release__(releases)
        else:
            if self.auth == "basic":
                req = requests.get(
                    f"{self.server}/{self.root_dir}",
                    auth=(self.user, self.password),
                    verify=self.verify)
            elif self.auth == "digest":
                req = requests.get(
                    f"{self.server}/{self.root_dir}",
                    auth=requests.auth.HTTPDigestAuth(self.user,
                                                      self.password),
                    verify=self.verify)
            else:
                req = requests.get(f"{self.server}/{self.root_dir}")

            releases = []
            status = req.status_code == requests.codes.ok

            if not status:
                req.raise_for_status()

            if not self.release:
                for rel in req.content.split():
                    rel = rel.decode()
                    rel = rel.strip("href=").strip("/").split(">")

                    if "-RELEASE" in rel[0]:
                        rel = rel[0].strip('"').strip("/").strip("/</a").strip(
                            'title="')

                        if rel not in releases:
                            releases.append(rel)

                if len(releases) == 0:
                    iocage_lib.ioc_common.logit(
                        {
                            "level":
                            "EXCEPTION",
                            "message":
                            f"""\
    No RELEASEs were found at {self.server}/{self.root_dir}!
    Please ensure the server is correct and the root-dir is
    pointing to a top-level directory with the format:
        - XX.X-RELEASE
        - XX.X-RELEASE
        - XX.X-RELEASE
    """
                        },
                        _callback=self.callback,
                        silent=self.silent)

                releases = iocage_lib.ioc_common.sort_release(
                    releases, fetch_releases=True)

                if _list:
                    return releases

                for r in releases:
                    if r in eol:
                        iocage_lib.ioc_common.logit(
                            {
                                "level": "INFO",
                                "message": f"[{releases.index(r)}] {r} (EOL)"
                            },
                            _callback=self.callback,
                            silent=self.silent)
                    else:
                        iocage_lib.ioc_common.logit(
                            {
                                "level": "INFO",
                                "message": f"[{releases.index(r)}] {r}"
                            },
                            _callback=self.callback,
                            silent=self.silent)

                host_release = iocage_lib.ioc_common.get_host_release()
                self.release = input("\nType the number of the desired"
                                     " RELEASE\nPress [Enter] to fetch "
                                     f"the default selection: ({host_release})"
                                     "\nType EXIT to quit: ")
                self.release = self.__fetch_validate_release__(releases)

        if self.hardened:
            self.root_dir = f"{rdir}/HardenedBSD-{self.release.upper()}-" \
                f"{self.arch}-LATEST"

        self.__fetch_exists__()
        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Fetching: {self.release}\n"
            },
            _callback=self.callback,
            silent=self.silent)
        self.fetch_download(self.files)
        missing_files = self.__fetch_check__(self.files)
        missing_attempt = 0

        while True:
            if not self.files_left:
                break

            if missing_attempt == 4:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': 'Max retries exceeded, one or more files'
                                   f' ({", ".join(missing_files)})'
                                   ' failed checksum verification!'
                    },
                    _callback=self.callback,
                    silent=self.silent)

            if not missing_files:
                missing_files = self.files_left

            self.fetch_download(missing_files, missing=bool(missing_files))
            missing_files = self.__fetch_check__(
                missing_files, _missing=bool(missing_files)
            )

            if missing_files:
                missing_attempt += 1

        if not self.hardened and self.update:
            self.fetch_update()

    def __fetch_exists__(self):
        """
        Checks if the RELEASE exists on the remote
        """
        release = f"{self.server}/{self.root_dir}/{self.release}"

        if self.auth == "basic":
            r = requests.get(
                release,
                auth=(self.user, self.password),
                verify=self.verify)
        elif self.auth == "digest":
            r = requests.get(
                release,
                auth=requests.auth.HTTPDigestAuth(
                    self.user, self.password),
                verify=self.verify)
        else:
            r = requests.get(
                release, verify=self.verify)

        if r.status_code == 404:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{self.release} was not found!"
                },
                _callback=self.callback,
                silent=self.silent)

    def __fetch_check__(self, _list, _missing=False):
        """
        Will check if every file we need exists, if they do we check the SHA256
        and make sure it matches the files they may already have.
        """
        hashes = {}
        missing = []
        files_left = self.files_left.copy()

        if os.path.isdir(f"{self.iocroot}/download/{self.release}"):
            os.chdir(f"{self.iocroot}/download/{self.release}")

            for _, _, files in os.walk("."):
                if "MANIFEST" not in files:
                    if self.server == "https://download.freebsd.org":
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'INFO',
                                'message': 'MANIFEST missing, downloading one'
                            },
                            _callback=self.callback,
                            silent=self.silent)
                        self.fetch_download(['MANIFEST'], missing=True)

            try:
                with open("MANIFEST", "r") as _manifest:
                    for line in _manifest:
                        col = line.split("\t")
                        hashes[col[0]] = col[1]
            except FileNotFoundError:
                if 'MANIFEST' not in self.files:
                    m_files = ' '.join([f'-F {x}' for x in self.files])
                    m = f'iocage fetch -r {self.release} -s {self.server}' \
                        f' -F MANIFEST {m_files}'
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': 'MANIFEST missing, refusing to continue'
                                       f'!\nEXAMPLE COMMAND: {m}'
                        },
                        _callback=self.callback,
                        silent=self.silent)

                self.fetch_download(['MANIFEST'], missing=True)
                with open("MANIFEST", "r") as _manifest:
                    for line in _manifest:
                        col = line.split("\t")
                        hashes[col[0]] = col[1]

            for f in files_left:
                if f == "MANIFEST":
                    if f in self.files_left:
                        self.files_left.remove(f)
                    continue

                if self.hardened and f == "lib32.txz":
                    continue

                # Python Central
                hash_block = 65536
                sha256 = hashlib.sha256()

                if f in _list:
                    try:
                        with open(f, "rb") as txz:
                            buf = txz.read(hash_block)

                            while len(buf) > 0:
                                sha256.update(buf)
                                buf = txz.read(hash_block)

                            if hashes[f] != sha256.hexdigest():
                                if not _missing:
                                    iocage_lib.ioc_common.logit(
                                        {
                                            "level":
                                            "WARNING",
                                            "message":
                                            f"{f} failed verification,"
                                            " will redownload!"
                                        },
                                        _callback=self.callback,
                                        silent=self.silent)
                                    missing.append(f)
                    except FileNotFoundError:
                        if not _missing:
                            iocage_lib.ioc_common.logit(
                                {
                                    "level":
                                    "WARNING",
                                    "message":
                                    f"{f} missing, will try to redownload!"
                                },
                                _callback=self.callback,
                                silent=self.silent)
                            missing.append(f)
                        else:
                            iocage_lib.ioc_common.logit(
                                {
                                    "level": "EXCEPTION",
                                    "message": "Too many failed verifications!"
                                },
                                _callback=self.callback,
                                silent=self.silent)
                    except KeyError:
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'WARNING',
                                'message': f'{f} missing from MANIFEST,'
                                           ' refusing to extract!'
                            },
                            _callback=self.callback,
                            silent=self.silent)
                        continue

                if not missing and f in _list:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"Extracting: {f}... "
                        },
                        _callback=self.callback,
                        silent=self.silent)

                    try:
                        self.fetch_extract(f)
                    except Exception:
                        raise

                    if f in self.files_left:
                        self.files_left.remove(f)

            return missing

    def fetch_download(self, _list, missing=False):
        """Creates the download dataset and then downloads the RELEASE."""
        dataset = f"{self.iocroot}/download/{self.release}"
        fresh = False

        if not os.path.isdir(dataset):
            fresh = True
            dataset = f"{self.pool}/iocage/download/{self.release}"

            try:
                # It may actually still exist, just unmounted.
                self.zpool.create(dataset, {"compression": "lz4"})
            except libzfs.ZFSException as err:
                if err.code == libzfs.Error.EXISTS:
                    pass
                else:
                    raise

            self.zfs.get_dataset(dataset).mount()

        if missing or fresh:
            os.chdir(f"{self.iocroot}/download/{self.release}")

            for f in _list:
                if self.hardened:
                    _file = f"{self.server}/{self.root_dir}/{f}"

                    if f == "lib32.txz":
                        continue
                else:
                    _file = f"{self.server}/{self.root_dir}/" \
                        f"{self.release}/{f}"

                if self.auth == "basic":
                    r = requests.get(
                        _file,
                        auth=(self.user, self.password),
                        verify=self.verify,
                        stream=True)
                elif self.auth == "digest":
                    r = requests.get(
                        _file,
                        auth=requests.auth.HTTPDigestAuth(
                            self.user, self.password),
                        verify=self.verify,
                        stream=True)
                else:
                    r = requests.get(
                        _file, verify=self.verify, stream=True)

                status = r.status_code == requests.codes.ok

                if not status:
                    r.raise_for_status()

                with open(f, "wb") as txz:
                    file_size = int(r.headers['Content-Length'])
                    chunk_size = 1024 * 1024
                    total = file_size / chunk_size
                    start = time.time()
                    dl_progress = 0
                    last_progress = 0

                    for i, chunk in enumerate(
                            r.iter_content(chunk_size=chunk_size), 1):
                            if chunk:
                                elapsed = time.time() - start
                                dl_progress += len(chunk)
                                txz.write(chunk)

                                progress = float(i) / float(total)
                                if progress >= 1.:
                                    progress = 1
                                progress = round(progress * 100, 0)

                                if progress != last_progress:
                                    text = self.update_progress(
                                        progress,
                                        f'Downloading: {f}',
                                        elapsed,
                                        chunk_size
                                    )

                                    if progress % 10 == 0:
                                        # Not for user output, but for callback
                                        # heartbeats
                                        iocage_lib.ioc_common.logit(
                                            {
                                                'level': 'INFO',
                                                'message': text.rstrip()
                                            },
                                            _callback=self.callback,
                                            silent=True)

                                last_progress = progress
                                start = time.time()

    def update_progress(self, progress, display_text, elapsed, chunk_size):
        """
        Displays or updates a console progress bar.
        Original source: https://stackoverflow.com/a/15860757/1391441
        """
        barLength, status = 20, ""

        current_time = chunk_size / elapsed
        current_time = round(current_time / 1000000, 1)

        block = int(round(barLength * (progress / 100)))

        if progress == 100:
            status = "\r\n"

        if self.silent:
            return

        text = "\r{} [{}] {:.0f}% {} {}MB/s".format(
            display_text,
            "#" * block + "-" * (barLength - block),
            progress, status, current_time)

        erase = '\x1b[2K'

        print(erase, text, end="\r")

        return text

    def __fetch_check_members__(self, members):
        """Checks if the members are relative, if not, log a warning."""
        _members = []

        for m in members:
            if m.name == ".":
                continue

            if ".." in m.name:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "WARNING",
                        "message":
                        f"{m.name} is not a relative file, skipping "
                    },
                    _callback=self.callback,
                    silent=self.silent)

                continue

            _members.append(m)

        return _members

    def fetch_extract(self, f):
        """
        Takes a src and dest then creates the RELEASE dataset for the data.
        """
        src = f"{self.iocroot}/download/{self.release}/{f}"
        dest = f"{self.iocroot}/releases/{self.release}/root"

        dataset = f"{self.pool}/iocage/releases/{self.release}/root"

        if not os.path.isdir(dest):
            self.zpool.create(dataset, {"compression": "lz4"},
                              libzfs.DatasetType.FILESYSTEM, 0, True)

            self.zfs.get_dataset(dataset).mount_recursive(True)

        with tarfile.open(src) as f:
            # Extracting over the same files is much slower then
            # removing them first.
            member = self.__fetch_extract_remove__(f)
            member = self.__fetch_check_members__(member)
            f.extractall(dest, members=member)

    def fetch_update(self, cli=False, uuid=None):
        """This calls 'freebsd-update' to update the fetched RELEASE."""
        tmp_dataset = self.zfs_get_dataset_name('/tmp')
        tmp_val = self.zfs_get_property(tmp_dataset, 'exec')

        if tmp_val == 'off':
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{tmp_dataset} needs exec=on!'
                },
                _callback=self.callback,
                silent=self.silent)

        if cli:
            cmd = [
                "mount", "-t", "devfs", "devfs",
                f"{self.iocroot}/jails/{uuid}/root/dev"
            ]
            mount = f'{self.iocroot}/jails/{uuid}'
            mount_root = f'{mount}/root'

            iocage_lib.ioc_common.logit(
                {
                    "level":
                    "INFO",
                    "message":
                    f"\n* Updating {uuid} to the latest patch"
                    " level... "
                },
                _callback=self.callback,
                silent=self.silent)
        else:
            cmd = [
                "mount", "-t", "devfs", "devfs",
                f"{self.iocroot}/releases/{self.release}/root/dev"
            ]
            mount = f'{self.iocroot}/releases/{self.release}'
            mount_root = f'{mount}/root'

            iocage_lib.ioc_common.logit(
                {
                    "level":
                    "INFO",
                    "message":
                    f"\n* Updating {self.release} to the latest patch"
                    " level... "
                },
                _callback=self.callback,
                silent=self.silent)

        su.Popen(cmd).communicate()
        shutil.copy("/etc/resolv.conf", f"{mount_root}/etc/resolv.conf")

        path = '/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:'\
               '/usr/local/bin:/root/bin'
        fetch_env = {
            'UNAME_r': self.release,
            'PAGER': '/bin/cat',
            'PATH': path,
            'PWD': '/',
            'HOME': '/',
            'TERM': 'xterm-256color'
        }

        if os.path.isfile(f"{mount_root}/etc/freebsd-update.conf"):
            if self.verify:
                f = "https://raw.githubusercontent.com/freebsd/freebsd" \
                    "/master/usr.sbin/freebsd-update/freebsd-update.sh"

                tmp = tempfile.NamedTemporaryFile(delete=False)
                with urllib.request.urlopen(f) as fbsd_update:
                    tmp.write(fbsd_update.read())
                tmp.close()
                os.chmod(tmp.name, 0o755)
                fetch_name = tmp.name
            else:
                fetch_name = f"{mount_root}/usr/sbin/freebsd-update"

            fetch_cmd = [
                fetch_name, "-b", mount_root, "-d",
                f"{mount_root}/var/db/freebsd-update/", "-f",
                f"{mount_root}/etc/freebsd-update.conf",
                "--not-running-from-cron", "fetch"
            ]
            with iocage_lib.ioc_exec.IOCExec(
                fetch_cmd,
                uuid,
                f"{self.iocroot}/jails/{uuid}",
                unjailed=True,
                callback=self.callback,
                su_env=fetch_env
            ) as _exec:
                iocage_lib.ioc_common.consume_and_log(
                    _exec, callback=self.callback)

            fetch_install_cmd = [
                fetch_name, "-b", mount_root, "-d",
                f"{mount_root}/var/db/freebsd-update/", "-f",
                f"{mount_root}/etc/freebsd-update.conf", "install"
            ]
            with iocage_lib.ioc_exec.IOCExec(
                fetch_install_cmd,
                uuid,
                f"{self.iocroot}/jails/{uuid}",
                unjailed=True,
                callback=self.callback,
                su_env=fetch_env
            ) as _exec:
                iocage_lib.ioc_common.consume_and_log(
                    _exec, callback=self.callback)

            if self.verify:
                # tmp only exists if they verify SSL certs

                if not tmp.closed:
                    tmp.close()

                os.remove(tmp.name)

        try:
            if not cli:
                # Why this sometimes doesn't exist, we may never know.
                os.remove(f"{mount_root}/etc/resolv.conf")
        except OSError:
            pass

        su.Popen(["umount", f"{mount_root}/dev"]).communicate()

        new_release = iocage_lib.ioc_common.get_jail_freebsd_version(
            mount_root, self.release
        )

        if self.release != new_release:
            jails = iocage_lib.ioc_list.IOCList(
                'uuid', hdr=False).list_datasets()

            for jail, path in jails.items():
                _json = iocage_lib.ioc_json.IOCJson(path)
                props = _json.json_get_value('all')

                if props.get('basejail', 'no') == 'yes':
                    if props['release'] == self.release:
                        props['release'] = new_release
                        _json.json_write(props)

        return new_release

    def __fetch_extract_remove__(self, tar):
        """
        Tries to remove any file that exists from the archive as overwriting
        is very slow in tar.
        """
        members = []

        for f in tar.getmembers():
            rel_path = f"{self.iocroot}/releases/{self.release}/root/" \
                f"{f.name}"
            try:
                # . and so forth won't like this.
                os.remove(rel_path)
            except (IOError, OSError):
                pass

            members.append(f)

        return members
