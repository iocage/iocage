"""iocage fetch module."""
import collections
import hashlib
import json
import logging
import os
import re
import shutil
import tarfile
from ftplib import FTP, error_perm
from shutil import copy
from subprocess import CalledProcessError, PIPE, Popen, STDOUT
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

import requests
from requests.auth import HTTPDigestAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from tqdm import tqdm

from iocage.lib.ioc_common import checkoutput, sort_release
from iocage.lib.ioc_create import IOCCreate
from iocage.lib.ioc_destroy import IOCDestroy
from iocage.lib.ioc_exec import IOCExec
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_start import IOCStart


class IOCFetch(object):
    """Fetch a RELEASE for use as a jail base."""

    def __init__(self, release, server="ftp.freebsd.org", user="anonymous",
                 password="anonymous@", auth=None, root_dir=None, http=False,
                 _file=False, verify=True, hardened=False, update=True,
                 eol=True, files=("MANIFEST", "base.txz", "lib32.txz",
                                  "doc.txz")):
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
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
        self.files = files
        self.update = update
        self.eol = eol

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

    def fetch_release(self, _list=False):
        """Small wrapper to choose the right fetch."""
        if self.http:
            if self.eol and self.verify:
                eol = self.__fetch_eol_check__()
            else:
                eol = []

            self.fetch_http_release(eol, _list=_list)
        elif self._file:
            # Format for file directory should be: root-dir/RELEASE/*.txz
            if not self.root_dir:
                raise RuntimeError("Please supply --root-dir or -d.")

            try:
                os.chdir("{}/{}".format(self.root_dir, self.release))
            except OSError as err:
                raise RuntimeError("{}".format(err))

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
                        error = "{} is a required file!".format(f) + \
                                "\nPlease place it in {}/{}".format(
                                    self.root_dir, self.release)
                    else:
                        error = "{}.txz is a required file!".format(f) \
                                + "\nPlease place it in {}/{}".format(
                            self.root_dir, self.release)
                    raise RuntimeError(error)

                self.lgr.info("Copying: {}... ".format(f))
                copy(f, dataset)

                self.lgr.info("Extracting: {}... ".format(f))
                self.fetch_extract(f)
        else:
            if self.eol and self.verify:
                eol = self.__fetch_eol_check__()
            else:
                eol = []

            self.fetch_ftp_release(eol, _list=_list)

    def fetch_http_release(self, eol, _list=False):
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

                releases = sort_release(releases)
                for r in releases:
                    self.lgr.info("[{}] {}".format(releases.index(r), r))
                self.release = input(
                    "\nWhich release do you want to fetch?"
                    " (EXIT) ")
                self.release = self.__fetch_validate_release__(releases)
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
                    rel = rel.decode("utf-8")
                    rel = rel.strip("href=").strip("/").split(">")
                    if "-RELEASE" in rel[0]:
                        rel = rel[0].strip('"').strip("/").strip("/</a")
                        if rel not in releases:
                            releases.append(rel)

                releases = sort_release(releases)
                for r in releases:
                    if r in eol:
                        self.lgr.info(
                            "[{}] {} (EOL)".format(releases.index(r), r))
                    else:
                        self.lgr.info("[{}] {}".format(releases.index(r), r))

                if _list:
                    return

                self.release = input(
                    "\nWhich release do you want to fetch?"
                    " (EXIT) ")
                self.release = self.__fetch_validate_release__(releases)

        if self.hardened:
            self.root_dir = "{}/hardenedbsd-{}-LAST".format(rdir,
                                                            self.release.lower())
        self.lgr.info("Fetching: {}\n".format(self.release))
        self.fetch_download(self.files)
        missing = self.__fetch_check__(self.files)

        if missing:
            self.fetch_download(missing, missing=True)
            self.__fetch_check__(missing, _missing=True)

        if not self.hardened:
            self.fetch_update()

    def fetch_ftp_release(self, eol, _list=False):
        """
        Fetch a user specified RELEASE from FreeBSD's ftp server or a user
        supplied one. The user can also specify the user, password and
        root-directory containing the release tree that looks like so:
            - XX.X-RELEASE
            - XX.X-RELEASE
            - XX.X_RELEASE
        """

        ftp = self.__fetch_ftp_connect__()
        ftp_list = ftp.nlst()

        if not self.release:
            releases = sort_release(ftp_list)
            for r in releases:
                if r in eol:
                    self.lgr.info("[{}] {} (EOL)".format(releases.index(r), r))
                else:
                    self.lgr.info("[{}] {}".format(releases.index(r), r))

            if _list:
                return

            self.release = input("\nWhich release do you want to fetch?"
                                 " (EXIT) ")

            self.release = self.__fetch_validate_release__(releases)

        # This has the benefit of giving us a list of files, but also as a
        # easy sanity check for the existence of the RELEASE before we reuse
        #  it below.
        try:
            ftp.cwd(self.release)
        except error_perm:
            raise RuntimeError("{} was not found!".format(self.release))

        ftp_list = self.files
        ftp.quit()

        self.lgr.info("Fetching: {}\n".format(self.release))
        self.fetch_download(ftp_list, ftp=True)
        missing = self.__fetch_check__(ftp_list, ftp=True)

        if missing:
            self.fetch_download(missing, ftp=True, missing=True)
            self.__fetch_check__(missing, ftp=True, _missing=True)

        if self.update:
            self.fetch_update()

    def __fetch_ftp_connect__(self):
        """
        Connects to the ftp server and returns the proper cwd for easy
        reconnection.
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

        return ftp

    def __fetch_check__(self, _list, ftp=False, _missing=False):
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
                        _ftp = self.__fetch_ftp_connect__()
                        _ftp.cwd(self.release)
                        _ftp.retrbinary("RETR MANIFEST", open("MANIFEST",
                                                              "wb").write)
                        _ftp.quit()
                    elif not ftp and self.server == \
                            "https://download.freebsd.org":
                        r = requests.get("{}/{}/{}/MANIFEST".format(
                            self.server, self.root_dir, self.release),
                            verify=self.verify, stream=True)

                        status = r.status_code == requests.codes.ok
                        if not status:
                            r.raise_for_status()

                        with open("MANIFEST", "wb") as txz:
                            shutil.copyfileobj(r.raw, txz)

            try:
                with open("MANIFEST", "r") as _manifest:
                    for line in _manifest:
                        col = line.split("\t")
                        hashes[col[0]] = col[1]
            except (IOError, OSError):
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
                        with open(f, "rb") as txz:
                            buf = txz.read(hash_block)

                            while len(buf) > 0:
                                sha256.update(buf)
                                buf = txz.read(hash_block)

                            if hashes[f] != sha256.hexdigest():
                                if not _missing:
                                    self.lgr.info("{} failed verification,"
                                                  " will redownload!".format(
                                        f))
                                    missing.append(f)
                                else:
                                    raise RuntimeError("Too many failed"
                                                       " verifications!")
                    except (IOError, OSError):
                        if not _missing:
                            self.lgr.error(
                                "{} missing, will download!".format(f))
                            missing.append(f)
                        else:
                            raise RuntimeError(
                                "Too many failed verifications!")

                if not missing:
                    self.lgr.info("Extracting: {}... ".format(f))

                    try:
                        self.fetch_extract(f)
                    except:
                        raise

            return missing

    def fetch_download(self, _list, ftp=False, missing=False):
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
                        _file = "{}/{}/{}/{}".format(self.server,
                                                     self.root_dir,
                                                     self.release, f)
                    if self.auth == "basic":
                        r = requests.get(_file,
                                         auth=(self.user, self.password),
                                         verify=self.verify, stream=True)
                    elif self.auth == "digest":
                        r = requests.get(_file, auth=HTTPDigestAuth(
                            self.user, self.password), verify=self.verify,
                                         stream=True)
                    else:
                        r = requests.get(_file, verify=self.verify,
                                         stream=True)

                    status = r.status_code == requests.codes.ok
                    if not status:
                        r.raise_for_status()

                    with open(f, "wb") as txz:
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
                    _ftp = self.__fetch_ftp_connect__()
                    _ftp.cwd(self.release)

                    if bool(re.compile(
                            r"MANIFEST|base.txz|lib32.txz|doc.txz").match(f)):
                        try:
                            _ftp.voidcmd('TYPE I')
                            filesize = _ftp.size(f)

                            with open(f, "wb") as txz:
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

                                _ftp.retrbinary("RETR {}".format(f), callback)
                                pbar.close()
                                _ftp.quit()
                        except:
                            raise
                    else:
                        pass

    def fetch_extract(self, f):
        """
        Takes a src and dest then creates the RELEASE dataset for the data.
        """
        src = "{}/download/{}/{}".format(self.iocroot, self.release, f)
        dest = "{}/releases/{}/root".format(self.iocroot, self.release)
        Popen(["zfs", "create", "-p", "-o", "compression=lz4",
               "{}/iocage/releases/{}/root".format(self.pool,
                                                   self.release)]).communicate()

        with tarfile.open(src) as f:
            # Extracting over the same files is much slower then
            # removing them first.
            member = self.__fetch_extract_remove__(f)
            f.extractall(dest, members=member)

    def fetch_update(self, cli=False, uuid=None, tag=None):
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
        if os.path.isfile(f"{new_root}/etc/freebsd-update.conf"):
            f = "https://raw.githubusercontent.com/freebsd/freebsd" \
                "/master/usr.sbin/freebsd-update/freebsd-update.sh"

            tmp = None
            try:
                tmp = NamedTemporaryFile(delete=False)
                with urlopen(f) as fbsd_update:
                    tmp.write(fbsd_update.read())
                tmp.close()
                os.chmod(tmp.name, 0o755)

                Popen([tmp.name, "-b", new_root, "-d",
                       "{}/var/db/freebsd-update/".format(new_root), "-f",
                       "{}/etc/freebsd-update.conf".format(new_root),
                       "fetch"], stderr=PIPE).communicate()

                Popen([tmp.name, "-b", new_root, "-d",
                       "{}/var/db/freebsd-update/".format(new_root), "-f",
                       "{}/etc/freebsd-update.conf".format(new_root),
                       "install"], stderr=PIPE).communicate()
            finally:
                if tmp:
                    if not tmp.closed:
                        tmp.close()

                    os.remove(tmp.name)
        try:
            if not cli:
                # Why this sometimes doesn't exist, we may never know.
                os.remove("{}/etc/resolv.conf".format(new_root))
        except OSError:
            pass

        Popen(["umount", "{}/dev".format(new_root)]).communicate()

    def fetch_plugin(self, _json, props, num):
        """Expects an JSON object."""
        with open(_json, "r") as j:
            conf = json.load(j)
        self.release = conf["release"]
        pkg_repos = conf["fingerprints"]
        freebsd_version = f"{self.iocroot}/releases/{conf['release']}" \
                          "/root/bin/freebsd-version"

        if num <= 1:
            self.lgr.info("Plugin: {}".format(conf["name"]))
            self.lgr.info("  Using RELEASE: {}".format(self.release))
            self.lgr.info(
                "  Post-install Artifact: {}".format(conf["artifact"]))
            self.lgr.info("  These pkgs will be installed:")

            for pkg in conf["pkgs"]:
                self.lgr.info("    - {}".format(pkg))

            if not os.path.isdir("{}/releases/{}".format(self.iocroot,
                                                         self.release)):
                self.fetch_release()

        if conf["release"][:4].endswith("-"):
            # 9.3-RELEASE and under don't actually have this binary.
            release = conf["release"]
        else:
            with open(freebsd_version, "r") as r:
                for line in r:
                    if line.startswith("USERLAND_VERSION"):
                        release = line.rstrip().partition("=")[2].strip(
                            '"')

        # We set our properties that we need, and then iterate over the user
        #  supplied properties replacing ours. Finally we add _1, _2 etc to
        # the tag with the final iteration if the user supplied count.
        create_props = [f"cloned_release={self.release}",
                        f"release={release}", "type=plugin"]

        # If the user supplied a tag, we shouldn't add ours.
        if "tag" not in [p.split("=")[0] for p in props]:
            _tag = f"tag={conf['name']}"
            create_props += [_tag]
        else:
            for p in props:
                _p = p.split("=")[0]
                _tag = p if _p == "tag" else ""

        create_props = [f"{k}={v}" for k, v in
                        (p.split("=") for p in props)] + create_props
        create_props = [f"{k}_{num}" if k == f"{_tag}" and num != 0 else k
                        for k in create_props]

        uuid = IOCCreate(self.release, create_props, 0).create_jail()
        jaildir = "{}/jails/{}".format(self.iocroot, uuid)
        repo_dir = "{}/root/usr/local/etc/pkg/repos".format(jaildir)
        _conf = IOCJson(jaildir).json_load()
        tag = _conf["tag"]

        # We do this test again as the user could supply a malformed IP to
        # fetch that bypasses the more naive check in cli/fetch
        if _conf["ip4_addr"] == "none" and _conf["ip6_addr"] == "none":
            self.lgr.error("\nAn IP address is needed to fetch a "
                           "plugin!\n")
            self.lgr.error("Destroying partial plugin.")
            IOCDestroy(uuid, tag, jaildir).destroy_jail()
            raise RuntimeError()

        IOCStart(uuid, tag, jaildir, _conf, silent=True)

        try:
            os.makedirs(repo_dir, 0o755)
        except OSError:
            # It exists, that's fine.
            pass

        for repo in pkg_repos:
            repo_name = repo
            repo = pkg_repos[repo]
            f_dir = "{}/root/usr/local/etc/pkg/fingerprints/{}/trusted".format(
                jaildir, repo_name)
            repo_conf = """\
{reponame}: {{
            url: "{packagesite}",
            signature_type: "fingerprints",
            fingerprints: "/usr/local/etc/pkg/fingerprints/{reponame}",
            enabled: true
            }}
"""

            try:
                os.makedirs(f_dir, 0o755)
            except OSError:
                self.lgr.error("Repo: {} already exists, skipping!".format(
                    repo_name))

            r_file = "{}/{}.conf".format(repo_dir, repo_name)

            with open(r_file, "w") as r_conf:
                r_conf.write(repo_conf.format(reponame=repo_name,
                                              packagesite=conf["packagesite"]))

            f_file = "{}/{}".format(f_dir, repo_name)

            for r in repo:
                finger_conf = """\
function: {function}
fingerprint: {fingerprint}
"""
                with open(f_file, "w") as f_conf:
                    f_conf.write(finger_conf.format(function=r["function"],
                                                    fingerprint=r[
                                                        "fingerprint"]))
        err = IOCCreate(self.release, create_props, 0, plugin=True,
                        pkglist=conf["pkgs"]).create_install_packages(uuid,
                                                                      jaildir,
                                                                      tag,
                                                                      _conf)
        if not err:
            # We need to pipe from tar to the root of the jail.
            if conf["artifact"]:
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
                    IOCExec(command, uuid, conf["name"], jaildir,
                            skip=True).exec_jail()
                except (IOError, OSError):
                    pass
        else:
            self.lgr.error("pkg error, refusing to fetch artifact and "
                           "run post_install.sh!\n")

    def fetch_plugin_index(self, props, _list=False):
        if self.server == "ftp.freebsd.org":
            git_server = "https://github.com/iXsystems/iocage-ix-plugins.git"
        else:
            git_server = self.server

        try:
            checkoutput(["git", "clone", git_server,
                         "{}/.plugin_index".format(self.iocroot)],
                        stderr=STDOUT)
        except CalledProcessError as err:
            if "already exists" in err.output.decode("utf-8").rstrip():
                try:
                    checkoutput(["git", "-C", "{}/.plugin_index".format(
                        self.iocroot), "pull"], stderr=STDOUT)
                except CalledProcessError as err:
                    raise RuntimeError("{}".format(
                        err.output.decode("utf-8").rstrip()))
            else:
                raise RuntimeError(
                    "{}".format(err.output.decode("utf-8").rstrip()))

        with open("{}/.plugin_index/INDEX".format(self.iocroot), "r") as \
                plugins:
            plugins = json.load(plugins)

        _plugins = self.__fetch_sort_plugin__(plugins)
        for p in _plugins:
            self.lgr.info("[{}] {}".format(_plugins.index(p), p))

        if _list:
            return

        plugin = input("\nWhich plugin do you want to create? (EXIT) ")
        plugin = self.__fetch_validate_plugin__(plugin.lower(), _plugins)
        self.fetch_plugin("{}/.plugin_index/{}.json".format(self.iocroot,
                                                            plugin), props, 0)

    def __fetch_validate_plugin__(self, plugin, plugins):
        """
        Checks if the user supplied an index number and returns the
        plugin. If they gave us a plugin name, we make sure that exists in
        the list at all.
        """
        if plugin.lower() == "exit":
            exit()

        if len(plugin) <= 2:
            try:
                plugin = plugins[int(plugin)]
            except IndexError:
                raise RuntimeError("[{}] is not in the list!".format(plugin))
            except ValueError:
                exit()
        else:
            # Quick list validation
            try:
                plugin = [i for i, p in enumerate(plugins) if
                          plugin.capitalize() in p]
                plugin = plugins[int(plugin[0])]
            except ValueError as err:
                raise RuntimeError("{}!".format(err))

        return plugin.split("(")[1].replace(")", "")

    def __fetch_sort_plugin__(self, plugins):
        """
        Sort the list by plugin.
        """
        p_dict = {}
        plugin_list = []

        for plugin in plugins:
            _plugin = "{} - {} ({})".format(plugins[plugin]["name"], plugins[
                plugin]["description"], plugin)
            p_dict[plugin] = _plugin

        ordered_p_dict = collections.OrderedDict(sorted(p_dict.items()))
        index = 0

        for p in ordered_p_dict.values():
            plugin_list.insert(index, "{}".format(p))
            index += 1

        return plugin_list

    def __fetch_extract_remove__(self, tar):
        """
        Tries to remove any file that exists from the archive as overwriting
        is very slow in tar.
        """
        members = []

        for f in tar.getmembers():
            rel_path = "{}/releases/{}/root/{}".format(self.iocroot,
                                                       self.release, f.name)
            try:
                # . and so forth won't like this.
                os.remove(rel_path)
            except (IOError, OSError):
                pass

            members.append(f)

        return members
