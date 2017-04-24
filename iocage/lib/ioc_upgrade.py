"""iocage upgrade module"""
import logging
import os
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

from iocage.lib.ioc_common import checkoutput
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


class IOCUpgrade(object):
    """Will upgrade a jail to the specified RELEASE."""

    def __init__(self, conf, new_release, path):
        self.lgr = logging.getLogger("ioc_upgrade")
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.freebsd_version = checkoutput(["freebsd-version"])
        self.conf = conf
        self.uuid = conf["host_hostuuid"]
        self.host_release = os.uname()[2]
        self.jail_release = conf["cloned_release"]
        self.new_release = new_release
        self.path = path
        self.status, self.jid = IOCList.list_get_jid(self.uuid)
        self._freebsd_version = f"{self.iocroot}/releases/" \
                                f"{new_release}/root/bin/freebsd-version"

    def upgrade_jail(self):
        if "HBSD" in self.freebsd_version:
            Popen(["hbsd-upgrade", "-j", self.jid]).communicate()
        else:
            os.environ["PAGER"] = "/bin/cat"
            if os.path.isfile(f"{self.path}/etc/freebsd-update.conf"):
                f = "https://raw.githubusercontent.com/freebsd/freebsd" \
                    "/master/usr.sbin/freebsd-update/freebsd-update.sh"

                tmp = None
                try:
                    tmp = NamedTemporaryFile(delete=False)
                    with urlopen(f) as fbsd_update:
                        tmp.write(fbsd_update.read())
                    tmp.close()
                    os.chmod(tmp.name, 0o755)

                    fetch = Popen([tmp.name, "-b", self.path, "-d",
                                   f"{self.path}/var/db/freebsd-update/",
                                   "-f",
                                   f"{self.path}/etc/freebsd-update.conf",
                                   "--not-running-from-cron",
                                   f"--currently-running {self.jail_release}",
                                   "-r",
                                   self.new_release, "upgrade"], stdin=PIPE)
                    fetch.communicate(b"y")

                    if fetch.returncode:
                        raise RuntimeError("Error occured, jail not upgraded!")

                    while not self.__upgrade_install__(tmp.name):
                        pass

                    if self.new_release[:4].endswith("-"):
                        # 9.3-RELEASE and under don't actually have this binary.
                        new_release = self.new_release
                    else:
                        with open(self._freebsd_version, "r") as r:
                            for line in r:
                                if line.startswith("USERLAND_VERSION"):
                                    new_release = line.rstrip().partition(
                                        "=")[2].strip('"')
                finally:
                    if tmp:
                        if not tmp.closed:
                            tmp.close()
                        os.remove(tmp.name)

                IOCJson(f"{self.path.replace('/root', '')}",
                        silent=True).json_set_value(f"release={new_release}")

                return new_release

    def __upgrade_install__(self, name):
        """Installs the upgrade and returns the exit code."""
        install = Popen([name, "-b", self.path, "-d",
                         f"{self.path}/var/db/freebsd-update/",
                         "-f",
                         f"{self.path}/etc/freebsd-update.conf",
                         "-r",
                         self.new_release, "install"], stderr=PIPE)
        install.communicate()

        return install.returncode
