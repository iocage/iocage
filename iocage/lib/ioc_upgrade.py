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
import os
import subprocess as su
import tempfile
import urllib.request

import iocage.lib.ioc_common
import iocage.lib.ioc_json
import iocage.lib.ioc_list


class IOCUpgrade(object):
    """Will upgrade a jail to the specified RELEASE."""

    def __init__(self, conf, new_release, path):
        self.pool = iocage.lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage.lib.ioc_json.IOCJson(self.pool).json_get_value(
            "iocroot")
        self.freebsd_version = iocage.lib.ioc_common.checkoutput(
            ["freebsd-version"])
        self.conf = conf
        self.uuid = conf["host_hostuuid"]
        self.host_release = os.uname()[2]
        self.cloned_release = conf["cloned_release"]
        self.jail_release = self.cloned_release if \
            self.cloned_release != "LEGACY_JAIL" else self.host_release
        self.new_release = new_release
        self.path = path
        self.status, self.jid = iocage.lib.ioc_list.IOCList.list_get_jid(
            self.uuid)
        self._freebsd_version = f"{self.iocroot}/jails/" \
                                f"{self.uuid}/root/bin/freebsd-version"

    def upgrade_jail(self):
        if "HBSD" in self.freebsd_version:
            su.Popen(["hbsd-upgrade", "-j", self.jid]).communicate()
            return

        os.environ["PAGER"] = "/bin/cat"
        if not os.path.isfile(f"{self.path}/etc/freebsd-update.conf"):
            return

        f = "https://raw.githubusercontent.com/freebsd/freebsd" \
            "/master/usr.sbin/freebsd-update/freebsd-update.sh"

        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            with urllib.request.urlopen(f) as fbsd_update:
                tmp.write(fbsd_update.read())
            tmp.close()
            os.chmod(tmp.name, 0o755)

            fetch = su.Popen([tmp.name, "-b", self.path, "-d",
                              f"{self.path}/var/db/freebsd-update/",
                              "-f",
                              f"{self.path}/etc/freebsd-update.conf",
                              "--not-running-from-cron",
                              "--currently-running "
                              f"{self.jail_release}",
                              "-r",
                              self.new_release, "upgrade"],
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
                            new_release = line.rstrip().partition(
                                "=")[2].strip('"')
        finally:
            if tmp:
                if not tmp.closed:
                    tmp.close()
                os.remove(tmp.name)

        iocage.lib.ioc_json.IOCJson(f"{self.path.replace('/root', '')}",
                                    silent=True).json_set_value(
            f"release={new_release}")

        return new_release

    def __upgrade_install__(self, name):
        """Installs the upgrade and returns the exit code."""
        install = su.Popen([name, "-b", self.path, "-d",
                            f"{self.path}/var/db/freebsd-update/",
                            "-f",
                            f"{self.path}/etc/freebsd-update.conf",
                            "-r",
                            self.new_release, "install"], stderr=su.PIPE)
        install.communicate()

        return install.returncode
