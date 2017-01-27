"""iocage fetch module."""
import contextlib
import hashlib
import json
import logging
import shutil
import tarfile
from ftplib import FTP
from shutil import copy
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile

import os
import re
import requests
from backports import lzma
from requests.auth import HTTPDigestAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from tqdm import tqdm

from iocage.lib.ioc_common import sort_release
from iocage.lib.ioc_create import IOCCreate
from iocage.lib.ioc_exec import IOCExec
from iocage.lib.ioc_json import IOCJson


class IOCFetch(object):
    """Fetch a RELEASE for use as a jail base."""

    def __init__(self, release, server="ftp.freebsd.org", user="anonymous",
                 password="anonymous@", auth=None, root_dir=None, http=False,
                 _file=False, verify=True, hardened=False):
        self.pool = IOCJson().get_prop_value("pool")
        self.iocroot = IOCJson(self.pool).get_prop_value("iocroot")
        self.server = server
        self.user = user
        self.password = password
        self.auth = auth

        if release:
            self.release = release.upper()
        else:
            self.release = release

        self.root_dir = root_dir
        self.lgr = logging.getLogger('ioc_fetch')
        self.arch = os.uname()[4]
        self.http = http
        self._file = _file
        self.verify = verify
        self.hardened = hardened
        self.files = ("MANIFEST", "base.txz", "lib32.txz", "doc.txz")

        if hardened:
            self.http = True

            if release:
                self.release = "{}-stable".format(self.release[:2]).upper()
            else:
                self.release = release

        if not verify:
            # The user likely knows this already.
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    @staticmethod
    def __eol_release__():
        """Scrapes the FreeBSD website and returns a list of EOL RELEASES"""
        logging.getLogger("requests").setLevel(logging.WARNING)
        _eol = "https://www.freebsd.org/security/unsupported.html"
        req = requests.get(_eol)
        status = req.status_code == requests.codes.ok
        eol_releases = []
        if not status:
            req.raise_for_status()

        for eol in req.content.split():
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

    def __validate_release__(self, releases):
        """
        Checks if the user supplied an index number and returns the
        RELEASE. If they gave us a full RELEASE, we make sure that exists in
        the list at all.
        """
        if self.release.lower() == "exit":
            exit()

        if len(self.release) <= 2:
            try:
                self.release = releases[int(self.release)]
            except IndexError:
                raise RuntimeError("[{}] is not in the list!".format(
                    self.release))
            except ValueError:
                rel = os.uname()[2]
                if "-RELEASE" in rel:
                    self.release = rel

                    # We want to use their host as RELEASE, but it may
                    # not be on the mirrors anymore.
                    try:
                        releases.index(self.release)
                    except ValueError:
                        raise RuntimeError("Please select an item!")
                else:
                    raise RuntimeError("Please select an item!")
        else:
            # Quick list validation
            try:
                releases.index(self.release)
            except ValueError as err:
                raise RuntimeError(err)

        return self.release

    def fetch_release(self):
        """Small wrapper to choose the right fetch."""
        if self.http:
            eol = self.__eol_release__()
            self.http_fetch_release(eol)
        elif self._file:
            # Format for file directory should be: root-dir/RELEASE/*.txz
            if not self.root_dir:
                raise RuntimeError("Please supply --root-dir or -d.")

            try:
                os.chdir("{}/{}".format(self.root_dir, self.release))
            except OSError as err:
                raise RuntimeError("ERROR: {}".format(err))

            if os.path.isdir(
                    "{}/download/{}".format(self.iocroot, self.release)):
                pass
            else:
                Popen(["zfs", "create", "-o", "compression=lz4",
                       "{}/iocage/download/{}".format(
                           self.pool,
                           self.release)]).communicate()
            dataset = "{}/download/{}".format(self.iocroot, self.release)

            for f in self.files:
                if not os.path.isfile(f):
                    Popen(["zfs", "destroy", "-r", "-f", "{}{}".format(
                        self.pool, dataset)])
                    if f == "MANIFEST":
                        error = "ERROR: {} is a required file!".format(f) + \
                                "\nPlease place it in {}/{}".format(
                                    self.root_dir, self.release)
                    else:
                        error = "ERROR: {}.txz is a required file!".format(f) \
                                + "\nPlease place it in {}/{}".format(
                            self.root_dir, self.release)
                    raise RuntimeError(error)

                self.lgr.info("Copying: {}... ".format(f))
                copy(f, dataset)

                self.lgr.info("Extracting: {}... ".format(f))
                self.extract_fetch(f)
        else:
            eol = self.__eol_release__()
            self.ftp_fetch_release(eol)

    def http_fetch_release(self, eol):
        """
        Fetch a user specified RELEASE from FreeBSD's http server or a user
        supplied one. The user can also specify the user, password and
        root-directory containing the release tree that looks like so:
            - XX.X-RELEASE
            - XX.X-RELEASE
            - XX.X_RELEASE
        """
        if self.hardened:
            if self.server == "ftp.freebsd.org":
                self.server = "http://installer.hardenedbsd.org"
                rdir = "releases/pub/HardenedBSD/releases/{0}/{0}".format(
                    self.arch)

        if self.server == "ftp.freebsd.org":
            self.server = "https://download.freebsd.org"
            self.root_dir = "ftp/releases/{}".format(self.arch)

        if self.auth and "https" not in self.server:
            self.server = "https://" + self.server
        elif "http" not in self.server:
            self.server = "http://" + self.server

        logging.getLogger("requests").setLevel(logging.WARNING)

        if self.hardened:
            if self.auth == "basic":
                req = requests.get("{}/releases".format(self.server),
                                   auth=(self.user, self.password),
                                   verify=self.verify)
            elif self.auth == "digest":
                req = requests.get("{}/releases".format(self.server),
                                   auth=HTTPDigestAuth(self.user,
                                                       self.password),
                                   verify=self.verify)
            else:
                req = requests.get("{}/releases".format(self.server))

            releases = []
            status = req.status_code == requests.codes.ok
            if not status:
                req.raise_for_status()

            if not self.release:
                for rel in req.content.split():
                    rel = rel.strip("href=").strip("/").split(">")
                    if "_stable" in rel[0]:
                        rel = rel[0].strip('"').strip("/").strip("/</a")
                        rel = rel.replace("hardened_", "").replace(
                            "_master-LAST", "").replace("_", "-").upper()
                        if rel not in releases:
                            releases.append(rel)

                releases = sort_release(releases, self.iocroot)
                for r in releases:
                    self.lgr.info("[{}] {}".format(releases.index(r), r))
                self.release = raw_input("\nWhich release do you want to fetch?"
                                         " (EXIT) ")
                self.release = self.__validate_release__(releases)
        else:
            if self.auth == "basic":
                req = requests.get("{}/{}".format(self.server, self.root_dir),
                                   auth=(self.user, self.password),
                                   verify=self.verify)
            elif self.auth == "digest":
                req = requests.get("{}/{}".format(self.server, self.root_dir),
                                   auth=HTTPDigestAuth(self.user,
                                                       self.password),
                                   verify=self.verify)
            else:
                req = requests.get("{}/{}".format(self.server, self.root_dir))

            releases = []
            status = req.status_code == requests.codes.ok
            if not status:
                req.raise_for_status()

            if not self.release:
                for rel in req.content.split():
                    rel = rel.strip("href=").strip("/").split(">")
                    if "-RELEASE" in rel[0]:
                        rel = rel[0].strip('"').strip("/").strip("/</a")
                        if rel not in releases:
                            releases.append(rel)

                releases = sort_release(releases, self.iocroot)
                for r in releases:
                    if r in eol:
                        self.lgr.info(
                            "[{}] {} (EOL)".format(releases.index(r), r))
                    else:
                        self.lgr.info("[{}] {}".format(releases.index(r), r))
                self.release = raw_input("\nWhich release do you want to fetch?"
                                         " (EXIT) ")
                self.release = self.__validate_release__(releases)

        if self.hardened:
            self.root_dir = "{}/hardenedbsd-{}-LAST".format(rdir,
                                                            self.release.lower())
        self.lgr.info("Fetching: {}\n".format(self.release))
        self.download_fetch(self.files)
        missing = self.__check_download__(self.files)

        if missing:
            self.download_fetch(missing, missing=True)
            self.__check_download__(missing, _missing=True)

        if not self.hardened:
            self.update_fetch()

    def ftp_fetch_release(self, eol):
        """
        Fetch a user specified RELEASE from FreeBSD's ftp server or a user
        supplied one. The user can also specify the user, password and
        root-directory containing the release tree that looks like so:
            - XX.X-RELEASE
            - XX.X-RELEASE
            - XX.X_RELEASE
        """
        ftp = FTP(self.server)
        ftp.login(user=self.user, passwd=self.password)

        if self.server == "ftp.freebsd.org":
            try:
                ftp.cwd("/pub/FreeBSD/releases/{}".format(self.arch))
            except:
                raise RuntimeError("{} was not found!".format(self.arch))
        elif self.root_dir:
            try:
                ftp.cwd(self.root_dir)
            except:
                raise RuntimeError("{} was not found!".format(self.root_dir))

        ftp_list = ftp.nlst()

        if not self.release:
            releases = sort_release(ftp_list, self.iocroot)
            for r in releases:
                if r in eol:
                    self.lgr.info("[{}] {} (EOL)".format(releases.index(r), r))
                else:
                    self.lgr.info("[{}] {}".format(releases.index(r), r))
            self.release = raw_input("\nWhich release do you want to fetch?"
                                     " (EXIT) ")

            self.release = self.__validate_release__(releases)

        ftp.cwd(self.release)
        ftp_list = ftp.nlst()

        self.lgr.info("Fetching: {}\n".format(self.release))
        self.download_fetch(ftp_list, ftp=ftp)
        missing = self.__check_download__(ftp_list, ftp=ftp)

        if missing:
            self.download_fetch(missing, ftp, missing=True)
            self.__check_download__(missing, ftp, _missing=True)

        ftp.quit()
        self.update_fetch()

    def __check_download__(self, _list, ftp=None, _missing=False):
        """
        Will check if every file we need exists, if they do we check the SHA256
        and make sure it matches the files they may already have.
        """
        hashes = {}
        missing = []

        if os.path.isdir("{}/download/{}".format(self.iocroot, self.release)):
            os.chdir("{}/download/{}".format(self.iocroot, self.release))

            for _, _, files in os.walk("."):
                if "MANIFEST" not in files:
                    if ftp and self.server == "ftp.freebsd.org":
                        ftp.retrbinary("RETR MANIFEST", open("MANIFEST",
                                                             "w").write)
                    elif not ftp and self.server == \
                            "https://download.freebsd.org":
                        r = requests.get("{}/{}/{}/MANIFEST".format(
                            self.server, self.root_dir, self.release),
                            verify=self.verify, stream=True)

                        status = r.status_code == requests.codes.ok
                        if not status:
                            r.raise_for_status()

                        with open("MANIFEST", "w") as txz:
                            shutil.copyfileobj(r.raw, txz)

            try:
                with open("MANIFEST") as _manifest:
                    for line in _manifest:
                        col = line.split("\t")
                        hashes[col[0]] = col[1]
            except IOError:
                raise RuntimeError("MANIFEST file is missing!")

            for f in self.files:
                if f == "MANIFEST":
                    continue

                if self.hardened and f == "lib32.txz":
                    continue

                # Python Central
                hash_block = 65536
                sha256 = hashlib.sha256()

                if f in _list:
                    try:
                        with open(f) as txz:
                            buf = txz.read(hash_block)

                            while len(buf) > 0:
                                sha256.update(buf)
                                buf = txz.read(hash_block)

                            if hashes[f] != sha256.hexdigest():
                                if not _missing:
                                    self.lgr.info("{} failed verification,"
                                                  " will redownload!".format(f))
                                    missing.append(f)
                                else:
                                    raise RuntimeError("Too many failed"
                                                       " verifications!")
                    except IOError:
                        if not _missing:
                            self.lgr.error(
                                "{} missing, will download!".format(f))
                            missing.append(f)
                        else:
                            raise RuntimeError("Too many failed verifications!")

                if not missing:
                    self.lgr.info("Extracting: {}... ".format(f))

                    try:
                        self.extract_fetch(f)
                    except:
                        raise

            return missing

    def download_fetch(self, _list, ftp=None, missing=False):
        """Creates the download dataset and then downloads the RELEASE."""
        dataset = "{}/download/{}".format(self.iocroot, self.release)
        fresh = False

        if not os.path.isdir(dataset):
            fresh = True
            Popen(["zfs", "create", "-o", "compression=lz4",
                   "{}/iocage/download/{}".format(self.pool,
                                                  self.release)]).communicate()

        if missing or fresh:
            os.chdir("{}/download/{}".format(self.iocroot, self.release))

            if self.http:
                for f in _list:
                    if self.hardened:
                        _file = "{}/{}/{}".format(self.server, self.root_dir,
                                                  f)
                        if f == "lib32.txz":
                            continue
                    else:
                        _file = "{}/{}/{}/{}".format(self.server, self.root_dir,
                                                     self.release, f)
                    if self.auth == "basic":
                        r = requests.get(_file, auth=(self.user, self.password),
                                         verify=self.verify, stream=True)
                    elif self.auth == "digest":
                        r = requests.get(_file, auth=HTTPDigestAuth(
                            self.user, self.password), verify=self.verify,
                                         stream=True)
                    else:
                        r = requests.get(_file, verify=self.verify, stream=True)

                    status = r.status_code == requests.codes.ok
                    if not status:
                        r.raise_for_status()

                    with open(f, "w") as txz:
                        pbar = tqdm(total=int(r.headers.get('content-length')),
                                    bar_format="{desc}{percentage:3.0f}%"
                                               " {rate_fmt}"
                                               " Elapsed: {elapsed}"
                                               " Remaining: {remaining}",
                                    unit="bit",
                                    unit_scale="mega")
                        pbar.set_description("Downloading: {}".format(f))

                        for chunk in r.iter_content(chunk_size=1024):
                            txz.write(chunk)
                            pbar.update(len(chunk))
                        pbar.close()
            elif ftp:
                for f in _list:
                    if bool(re.compile(
                            r"MANIFEST|base.txz|lib32.txz|doc.txz").match(
                        f)):
                        try:
                            ftp.voidcmd('TYPE I')
                            filesize = ftp.size(f)

                            with open(f, "w") as txz:
                                pbar = tqdm(total=filesize,
                                            bar_format="{desc}{"
                                                       "percentage:3.0f}%"
                                                       " {rate_fmt}"
                                                       " Elapsed: {elapsed}"
                                                       " Remaining: {"
                                                       "remaining}",
                                            unit="bit",
                                            unit_scale="mega")
                                pbar.set_description(
                                    "Downloading: {}".format(f))

                                def callback(chunk):
                                    txz.write(chunk)
                                    pbar.update(len(chunk))

                                ftp.retrbinary("RETR {}".format(f), callback)
                                pbar.close()
                        except:
                            raise
                    else:
                        pass

    def extract_fetch(self, f):
        """
        Takes a src and dest then creates the RELEASE dataset for the data.
        """
        src = "{}/download/{}/{}".format(self.iocroot, self.release, f)
        dest = "{}/releases/{}/root".format(self.iocroot, self.release)
        Popen(["zfs", "create", "-p", "-o", "compression=lz4",
               "{}/iocage/releases/{}/root".format(self.pool,
                                                   self.release)]).communicate()

        with contextlib.closing(lzma.LZMAFile(src)) as xz:
            with tarfile.open(fileobj=xz) as tar:
                tar.extractall(dest)

    def update_fetch(self, cli=False, uuid=None, tag=None):
        """This calls 'freebsd-update' to update the fetched RELEASE."""
        if cli:
            cmd = ["mount", "-t", "devfs", "devfs",
                   "{}/jails/{}/root/dev".format(self.iocroot, uuid)]
            new_root = "{}/jails/{}/root".format(self.iocroot, uuid)

            self.lgr.info(
                "\n* Updating {} ({}) to the latest patch level... ".format(
                    uuid, tag))
        else:
            cmd = ["mount", "-t", "devfs", "devfs",
                   "{}/releases/{}/root/dev".format(self.iocroot,
                                                    self.release)]
            new_root = "{}/releases/{}/root".format(self.iocroot, self.release)

            self.lgr.info(
                "\n* Updating {} to the latest patch level... ".format(
                    self.release))

        Popen(cmd).communicate()
        copy("/etc/resolv.conf", "{}/etc/resolv.conf".format(new_root))

        os.environ["UNAME_r"] = self.release
        os.environ["PAGER"] = "/bin/cat"
        if os.path.isfile("{}/etc/freebsd-update.conf".format(new_root)):
            # 10.1-RELEASE and under have a interactive check
            if float(self.release.partition("-")[0][:5]) <= 10.1:
                with NamedTemporaryFile(delete=False) as tmp_conf:
                    conf = "{}/usr/sbin/freebsd-update".format(new_root)
                    with open(conf) as update_conf:
                        for line in update_conf:
                            tmp_conf.write(re.sub("\[ ! -t 0 \]", "false",
                                                  line))
                os.chmod(tmp_conf.name, 0o755)
                Popen([tmp_conf.name, "-b", new_root, "-d",
                       "{}/var/db/freebsd-update/".format(new_root), "-f",
                       "{}/etc/freebsd-update.conf".format(new_root),
                       "fetch"], stderr=PIPE).communicate()
                os.remove(tmp_conf.name)
            else:
                Popen(["freebsd-update", "-b", new_root, "-d",
                       "{}/var/db/freebsd-update/".format(new_root), "-f",
                       "{}/etc/freebsd-update.conf".format(new_root),
                       "fetch"], stderr=PIPE).communicate()

            Popen(["freebsd-update", "-b", new_root, "-d",
                   "{}/var/db/freebsd-update/".format(new_root), "-f",
                   "{}/etc/freebsd-update.conf".format(new_root),
                   "install"], stderr=PIPE).communicate()

        try:
            # Why this sometimes doesn't exist, we may never know.
            os.remove("{}/etc/resolv.conf".format(new_root))
        except OSError:
            pass

        Popen(["umount", "{}/dev".format(new_root)]).communicate()

    def fetch_plugin(self, _json, props, num):
        """Expects an JSON object."""
        prop_dict = False
        with open(_json) as j:
            conf = json.load(j)
        self.release = conf["release"]

        if num <= 1:
            self.lgr.info("Plugin: {}".format(conf["name"]))
            self.lgr.info("  Using RELEASE: {}".format(self.release))
            self.lgr.info(
                "  Post-install Artifact: {}".format(conf["artifact"]))
            self.lgr.info("  These pkgs will be installed:")

            for pkg in conf["pkgs"]:
                self.lgr.info("    - {}".format(pkg))

            if os.path.isdir("{}/releases/{}".format(self.iocroot,
                                                     self.release)):
                self.lgr.info(
                    " RELEASE: {} already fetched.".format(self.release))
            else:
                self.lgr.info("\nFetching RELEASE: {}".format(self.release))
                self.fetch_release()

        # If no user supplied props exist, we need to add a tag prop as a dict.
        # Which requires the different for loop below.
        new_props = dict(release=self.release, type="plugin", tag=conf["name"])
        if props == ():
            props = {}
            props["tag"] = conf["name"]
            prop_dict = True

        if prop_dict:
            for k, v in props.iteritems():
                new_props[k] = v
        else:
            for p in props:
                key, _, value = p.partition("=")
                new_props[key] = value

        # If the user supplies some properties but NOT a tag, this is
        # important.
        for key, value in new_props.iteritems():
            if key == "tag":
                if num != 0:
                    value = "{}_{}".format(value, num)
                else:
                    value = "{}".format(value)
            new_props[key] = value

        uuid = IOCCreate(self.release, new_props, 0, conf["pkgs"],
                         True).create_jail()

        # We need to pipe from tar to the root of the jail.
        if conf["artifact"]:
            jaildir = "{}/jails/{}".format(self.iocroot, uuid)
            # TODO: Fancier.
            self.lgr.info("Fetching artifact... ")

            Popen(["git", "clone", conf["artifact"],
                   "{}/plugin".format(jaildir)],
                  stdout=PIPE, stderr=PIPE).communicate()
            tar_in = Popen(["tar", "cvf", "-", "-C",
                            "{}/plugin/overlay/".format(jaildir), "."],
                           stdout=PIPE, stderr=PIPE).communicate()
            Popen(["tar", "xf", "-", "-C", "{}/root".format(jaildir)],
                  stdin=PIPE).communicate(input=tar_in[0])

            try:
                copy("{}/plugin/post_install.sh".format(jaildir),
                     "{}/root/root".format(jaildir))

                self.lgr.info("Running post_install.sh")
                command = ["sh", "/root/post_install.sh"]
                IOCExec(command, uuid, conf["name"], "{}/root".format(
                    jaildir), plugin=True, plugin_dir=jaildir).exec_jail()
            except IOError:
                pass
