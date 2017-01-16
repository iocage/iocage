"""iocage fetch module."""
import contextlib
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

from iocage.lib.ioc_create import IOCCreate
from iocage.lib.ioc_exec import IOCExec
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_common import sort_release


class IOCFetch(object):
    """Fetch a RELEASE for use as a jail base."""

    def __init__(self, server, user, password, auth, release, root_dir, http,
                 _file):
        self.pool = IOCJson("").get_prop_value("pool")
        self.iocroot = IOCJson(self.pool).get_prop_value("iocroot")
        self.server = server
        self.user = user
        self.password = password
        self.auth = auth
        self.release = release
        self.root_dir = root_dir
        self.lgr = logging.getLogger('ioc_fetch')
        self.arch = os.uname()[4]
        self.http = http
        self._file = _file
        self.files = ("base.txz", "lib32.txz", "doc.txz")

    def __validate_release(self, releases):
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
            self.http_fetch_release()
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
                # TODO: Fancier
                if not os.path.isfile(f):
                    Popen(["zfs", "destroy", "-r", "-f", "{}{}".format(
                            self.pool, dataset)])
                    raise RuntimeError("ERROR: {}.txz is a required "
                                       "file!".format(f) +
                                       "\nPlease place it in {}/{}".format(
                                               self.root_dir, self.release))
                self.lgr.info("Copying: {}... ".format(f))
                copy(f, dataset)

                # TODO: Fancier.
                self.lgr.info("Extracting: {}... ".format(f))
                self.extract_fetch(f)
        else:
            self.ftp_fetch_release()

    def http_fetch_release(self):
        """
        Fetch a user specified RELEASE from FreeBSD's http server or a user
        supplied one. The user can also specify the user, password and
        root-directory containing the release tree that looks like so:
            - XX.X-RELEASE
            - XX.X-RELEASE
            - XX.X_RELEASE
        """
        if self.server == "ftp.freebsd.org":
            self.server = "https://download.freebsd.org"
            self.root_dir = "ftp/releases/{}".format(self.arch)

        if self.auth and "https" not in self.server:
            self.server = "https://" + self.server
        elif "http" not in self.server:
            self.server = "http://" + self.server

        logging.getLogger("requests").setLevel(logging.WARNING)

        if self.auth == "basic":
            req = requests.get("{}/{}".format(self.server, self.root_dir),
                               auth=(self.user, self.password))
        elif self.auth == "digest":
            req = requests.get("{}/{}".format(self.server, self.root_dir),
                               auth=HTTPDigestAuth(self.user,
                                                   self.password))
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

            releases = sort_release(releases)
            for r in releases:
                self.lgr.info("[{}] {}".format(releases.index(r), r))
            self.release = raw_input("\nWhich release do you want to fetch?"
                                     " (EXIT) ")
            self.release = self.__validate_release(releases)

        self.download_fetch(self.files)
        self.update_fetch()

    def ftp_fetch_release(self):
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
            releases = sort_release(ftp_list)
            for r in releases:
                self.lgr.info("[{}] {}".format(releases.index(r), r))
            self.release = raw_input("\nWhich release do you want to fetch?"
                                     " (EXIT) ")

            self.release = self.__validate_release(releases)

        ftp.cwd(self.release)
        ftp_list = ftp.nlst()
        self.download_fetch(ftp_list, ftp=ftp)
        ftp.quit()
        self.update_fetch()

    def download_fetch(self, _list, ftp=None):
        """Creates the download dataset and then downloads the RELEASE."""
        self.lgr.info("Fetching: {}\n".format(self.release))
        if os.path.isdir("{}/download/{}".format(self.iocroot, self.release)):
            pass
        else:
            Popen(["zfs", "create", "-o", "compression=lz4",
                   "{}/iocage/download/{}".format(self.pool,
                                                  self.release)]).communicate()

        os.chdir("{}/download/{}".format(self.iocroot, self.release))
        if self.http:
            for f in _list:
                if self.auth == "basic":
                    r = requests.get("{}/{}/{}/{}".format(
                            self.server, self.root_dir, self.release, f),
                            auth=(self.user, self.password), stream=True)
                elif self.auth == "digest":
                    r = requests.get("{}/{}/{}/{}".format(
                            self.server, self.root_dir, self.release, f),
                            auth=HTTPDigestAuth(self.user, self.password),
                            stream=True)
                else:
                    r = requests.get("{}/{}/{}/{}".format(
                            self.server, self.root_dir, self.release, f),
                            stream=True)

                status = r.status_code == requests.codes.ok
                if not status:
                    r.raise_for_status()

                with open(f, "w") as txz:
                    # TODO: Fancier.
                    self.lgr.info("Downloading: {}... ".format(f))
                    shutil.copyfileobj(r.raw, txz)
                del r

                # TODO: Fancier.
                self.lgr.info("Extracting: {}... ".format(f))
                try:
                    self.extract_fetch(f)
                except:
                    raise
        elif ftp:
            for f in _list:
                if bool(re.compile(r"base.txz|lib32.txz|doc.txz").match(f)):
                    try:
                        # TODO: Fancier.
                        self.lgr.info("Downloading: {}... ".format(f))
                        ftp.retrbinary("RETR {}".format(f), open(f, "w").write)

                        # TODO: Fancier.
                        self.lgr.info("Extracting: {}... ".format(f))
                        self.extract_fetch(f)
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

    def update_fetch(self):
        """This calls 'freebsd-update' to update the fetched RELEASE."""
        Popen(["mount", "-t", "devfs", "devfs",
               "{}/releases/{}/root/dev".format(self.iocroot,
                                                self.release)]).communicate()
        copy("/etc/resolv.conf",
             "{}/releases/{}/root/etc/resolv.conf".format(self.iocroot,
                                                          self.release))

        # TODO: Check for STABLE/PRERELEASE/CURRENT/BETA if we support those.
        # TODO: Fancier.
        self.lgr.info("\n* Updating {} to the latest patch level... ".format(
                self.release))

        os.environ["UNAME_r"] = self.release
        os.environ["PAGER"] = "/bin/cat"
        new_root = "{}/releases/{}/root".format(self.iocroot, self.release)
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
                       "fetch"], stdout=PIPE, stderr=PIPE).communicate()
                os.remove(tmp_conf.name)
            else:
                Popen(["freebsd-update", "-b", new_root, "-d",
                       "{}/var/db/freebsd-update/".format(new_root), "-f",
                       "{}/etc/freebsd-update.conf".format(new_root),
                       "fetch"], stdout=PIPE, stderr=PIPE).communicate()

            Popen(["freebsd-update", "-b", new_root, "-d",
                   "{}/var/db/freebsd-update/".format(new_root), "-f",
                   "{}/etc/freebsd-update.conf".format(new_root),
                   "install"], stdout=PIPE, stderr=PIPE).communicate()

        try:
            # Why this sometimes doesn't exist, we may never know.
            os.remove("{}/releases/{}/root/etc/resolv.conf".format(
                    self.iocroot, self.release))
        except OSError:
            pass

        Popen(["umount", "{}/releases/{}/root/dev".format(
                self.iocroot, self.release)]).communicate()

    def fetch_plugin(self, _json, props, num):
        """Expects an JSON object."""
        prop_dict = False
        # TODO: Check if the filename is resolvable on the filesystem, otherwise
        # check our GitHub repo. Unless it starts with git://, http(s)://
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
