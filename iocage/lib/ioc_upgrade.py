# Copyright (c) 2014-2017, iocage
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
"""iocage upgrade module"""
import datetime
import fileinput
import os
import pathlib
import subprocess as su
import tempfile
import urllib.request

import iocage.lib.ioc_common
import iocage.lib.ioc_json
import iocage.lib.ioc_list


class IOCUpgrade(object):

    """Will upgrade a jail to the specified RELEASE."""

    def __init__(self,
                 conf,
                 new_release,
                 path,
                 silent=False,
                 callback=None,
                 exit_on_error=False):
        self.pool = iocage.lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage.lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.freebsd_version = iocage.lib.ioc_common.checkoutput(
            ["freebsd-version"])
        self.conf = conf
        self.uuid = conf["host_hostuuid"]
        self.host_release = os.uname()[2]
        self.cloned_release = conf["cloned_release"]
        _release = conf["release"].rsplit("-", 1)[0]
        self.jail_release = _release if "-RELEASE" in _release else \
            conf["release"]
        self.new_release = new_release
        self.path = path
        self.status, self.jid = iocage.lib.ioc_list.IOCList.list_get_jid(
            self.uuid)
        self._freebsd_version = f"{self.iocroot}/jails/" \
            f"{self.uuid}/root/bin/freebsd-version"
        self.date = datetime.datetime.utcnow().strftime("%F")
        self.silent = silent
        self.callback = callback
        self.exit_on_error = exit_on_error

    def upgrade_jail(self):
        if "HBSD" in self.freebsd_version:
            su.Popen(["hbsd-upgrade", "-j", self.jid]).communicate()

            return

        os.environ["PAGER"] = "/bin/cat"

        if not os.path.isfile(f"{self.path}/etc/freebsd-update.conf"):
            return

        self.__upgrade_check_conf__()

        f = "https://raw.githubusercontent.com/freebsd/freebsd" \
            "/master/usr.sbin/freebsd-update/freebsd-update.sh"

        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            with urllib.request.urlopen(f) as fbsd_update:
                tmp.write(fbsd_update.read())
            tmp.close()
            os.chmod(tmp.name, 0o755)

            fetch = su.Popen(
                [
                    tmp.name, "-b", self.path, "-d",
                    f"{self.path}/var/db/freebsd-update/", "-f",
                    f"{self.path}/etc/freebsd-update.conf",
                    "--not-running-from-cron", "--currently-running "
                    f"{self.jail_release}", "-r", self.new_release, "upgrade"
                ],
                stdin=su.PIPE)
            fetch.communicate(b"y")

            if fetch.returncode:
                raise RuntimeError("Error occured, jail not upgraded!")

            while not self.__upgrade_install__(tmp.name):
                pass

            if self.new_release[:4].endswith("-"):
                # 9.3-RELEASE and under don't actually have this binary
                new_release = self.new_release
            else:
                with open(self._freebsd_version, "r") as r:
                    for line in r:
                        if line.startswith("USERLAND_VERSION"):
                            new_release = line.rstrip().partition("=")[
                                2].strip('"')
        finally:
            if tmp:
                if not tmp.closed:
                    tmp.close()
                os.remove(tmp.name)

        iocage.lib.ioc_json.IOCJson(
            f"{self.path.replace('/root', '')}",
            silent=True).json_set_value(f"release={new_release}")

        return new_release

    def upgrade_basejail(self, snapshot=True):
        if "HBSD" in self.freebsd_version:
            # TODO: Not supported yet
            msg = "Upgrading basejails on HardenedBSD is not supported yet."
            iocage.lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        os.environ["PAGER"] = "/bin/cat"
        release_p = pathlib.Path(f"{self.iocroot}/releases/{self.new_release}")
        self._freebsd_version = f"{self.iocroot}/releases/"\
            f"{self.new_release}/root/bin/freebsd-version"

        if not release_p.exists():
            msg = f"{self.new_release} is missing, please fetch it!"
            iocage.lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        if snapshot:
            self.__snapshot_jail__()

        p = pathlib.Path(
            f"{self.iocroot}/releases/{self.new_release}/root/usr/src")
        p_files = []

        if p.exists():
            for f in p.iterdir():
                # We want to make sure files actually exist as well
                p_files.append(f)

        if not p_files:
            msg = f"{self.new_release} is missing 'src.txz', please refetch!"
            iocage.lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        self.__upgrade_replace_basejail_paths__()
        ioc_up_dir = pathlib.Path(f"{self.path}/iocage_upgrade")

        if not ioc_up_dir.exists():
            ioc_up_dir.mkdir(exist_ok=True, parents=True)

        mount = su.Popen([
            "mount_nullfs", "-o", "ro",
            f"{self.iocroot}/releases/{self.new_release}/root/usr/src",
            f"{self.path}/iocage_upgrade"
        ])
        mount.communicate()

        if mount.returncode != 0:
            msg = "Mounting src into jail failed! Rolling back snapshot."
            self.__rollback_jail__()

            iocage.lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        # etcupdate = su.Popen([
            # "etcupdate", "-D", self.path, "-F", "-s",
            # f"{self.iocroot}/releases/{self.new_release}/root/usr/src"
        # ])
        # print(
            # f"etcupdate -D {self.path} -F -s"
            # f" {self.iocroot}/releases/{self.new_release}/root/usr/src")
        # etcupdate.communicate()
        stdout = None if not self.silent else su.DEVNULL
        stderr = None if self.silent else su.DEVNULL

        etcupdate = su.Popen([
            "jexec", f"ioc-{self.uuid.replace('.', '_')}",
            "/usr/sbin/etcupdate", "-F", "-s", "/iocage_upgrade"
        ], stdout=stdout, stderr=stderr)
        etcupdate.communicate()

        if etcupdate.returncode != 0:
            # These are now the result of a failed merge, nuking and putting
            # the backup back
            msg = "etcupdate failed! Rolling back snapshot."
            self.__rollback_jail__()

            su.Popen([
                "umount", "-f", f"{self.path}/iocage_upgrade"
            ]).communicate()

            iocage.lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                exit_on_error=self.exit_on_error,
                _callback=self.callback,
                silent=self.silent)

        if self.new_release[:4].endswith("-"):
            # 9.3-RELEASE and under don't actually have this binary
            new_release = self.new_release
        else:
            with open(self._freebsd_version, "r") as r:
                for line in r:
                    if line.startswith("USERLAND_VERSION"):
                        new_release = line.rstrip().partition("=")[2].strip(
                            '"')

        iocage.lib.ioc_json.IOCJson(
            f"{self.path.replace('/root', '')}",
            silent=True).json_set_value(f"release={new_release}")

        mq = pathlib.Path(f"{self.path}/var/spool/mqueue")

        if not mq.exists():
            mq.mkdir(exist_ok=True, parents=True)

        su.check_call([
            "jexec", f"ioc-{self.uuid.replace('.', '_')}", "newaliases"
        ], stdout=stdout, stderr=stderr)
        su.Popen([
            "umount", "-f", f"{self.path}/iocage_upgrade"
        ]).communicate()

        return new_release

    def __upgrade_install__(self, name):
        """Installs the upgrade and returns the exit code."""
        install = su.Popen(
            [
                name, "-b", self.path, "-d",
                f"{self.path}/var/db/freebsd-update/", "-f",
                f"{self.path}/etc/freebsd-update.conf", "-r", self.new_release,
                "install"
            ],
            stderr=su.PIPE,
            stdout=su.PIPE)

        for i in install.stdout:
            i = i.decode().rstrip()
            iocage.lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": i
                },
                _callback=self.callback,
                silent=self.silent)

            if i == "No updates are available to install.":
                return True

        return False

    def __upgrade_check_conf__(self):
        """
        Replaces freebsd-update.conf's default Components configuration to not
        update kernel
        """
        f = f"{self.path}/etc/freebsd-update.conf"
        text = "Components src world kernel"
        replace = "Components src world"

        self.__upgrade_replace_text__(f, text, replace)

    def __upgrade_replace_basejail_paths__(self):
        f = f"{self.iocroot}/jails/{self.uuid}/fstab"
        self.__upgrade_replace_text__(f, self.jail_release, self.new_release)

    @staticmethod
    def __upgrade_replace_text__(path, text, replace):
        with fileinput.FileInput(path, inplace=True, backup=".bak") as _file:
            for line in _file:
                print(line.replace(text, replace), end='')

        os.remove(f"{path}.bak")

    def __snapshot_jail__(self):
        import iocage.lib.iocage as ioc  # Avoids dep issues
        name = f"ioc_upgrade_{self.date}"
        ioc.IOCage(jail=self.uuid, exit_on_error=self.exit_on_error,
                   skip_jails=True, silent=True).snapshot(name)

    def __rollback_jail__(self):
        import iocage.lib.iocage as ioc  # Avoids dep issues
        name = f"ioc_upgrade_{self.date}"
        iocage = ioc.IOCage(jail=self.uuid, exit_on_error=self.exit_on_error,
                            skip_jails=True, silent=True)
        iocage.stop()
        iocage.rollback(name)
