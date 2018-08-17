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
"""iocage exec module."""
import subprocess as su

import iocage_lib.ioc_common
import iocage_lib.ioc_json
import iocage_lib.ioc_list
import iocage_lib.ioc_start
import select


class IOCExec(object):

    """Run jexec with a user inside the specified jail."""

    def __init__(self,
                 command,
                 uuid,
                 path,
                 host_user="root",
                 jail_user=None,
                 plugin=False,
                 pkg=False,
                 skip=False,
                 console=False,
                 silent=False,
                 msg_return=False,
                 msg_err_return=False,
                 callback=None):
        self.command = command
        self.uuid = uuid.replace(".", "_")
        self.path = path
        self.host_user = host_user
        self.jail_user = jail_user
        self.plugin = plugin
        self.pkg = pkg
        self.skip = skip
        self.console = console
        self.silent = silent
        self.msg_return = msg_return
        self.msg_err_return = msg_err_return
        self.callback = callback

    def exec_jail(self):
        if self.jail_user:
            flag = "-U"
            user = self.jail_user
        else:
            flag = "-u"
            user = self.host_user

        status, _ = iocage_lib.ioc_list.IOCList().list_get_jid(self.uuid)
        conf = iocage_lib.ioc_json.IOCJson(self.path).json_load()
        exec_fib = conf["exec_fib"]

        if not status:
            if not self.plugin and not self.skip:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": f"{self.uuid} is not running, starting jail"
                    },
                    _callback=self.callback,
                    silent=self.silent)

            if conf["type"] in ("jail", "plugin", "pluginv2", "clonejail"):
                iocage_lib.ioc_start.IOCStart(
                    self.uuid, self.path, conf, silent=True)
            elif conf["type"] == "basejail":
                iocage_lib.ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        "Please run \"iocage migrate\" before trying"
                        f" to start {self.uuid}"
                    },
                    _callback=self.callback,
                    silent=self.silent)
            elif conf["type"] == "template":
                iocage_lib.ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        "Please convert back to a jail before trying"
                        f" to start {self.uuid}"
                    },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                iocage_lib.ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        f"{conf['type']} is not a supported jail"
                        " type."
                    },
                    _callback=self.callback,
                    silent=self.silent)

            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": "\nCommand output:"
                },
                _callback=self.callback,
                silent=self.silent)

        if self.console:
            login_flags = conf["login_flags"].split()
            su.Popen([
                "setfib", exec_fib, "jexec", f"ioc-{self.uuid}", "login"
            ] + login_flags).communicate()

            return None, False
        else:
            try:
                if not self.pkg:
                    cmd = [
                        "setfib", exec_fib, "jexec", flag, user,
                        f"ioc-{self.uuid}"
                    ] + list(self.command)
                else:
                    cmd = self.command

                if self.msg_return or self.msg_err_return:
                    p = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE,
                                 close_fds=True, bufsize=1)

                    rtrn_stdout = b''
                    rtrn_stderr = b''

                    while True:
                        r = select.select([p.stdout.fileno(),
                                           p.stderr.fileno()], [], [], 0.5)[0]
                        if r:
                            if p.stdout.fileno() in r:
                                rtrn_stdout += p.stdout.readline()
                            if p.stderr.fileno() in r:
                                rtrn_stderr += p.stderr.readline()

                        if p.poll() is not None:
                            break

                    p.stdout.close()
                    p.stderr.close()

                    error = True if p.returncode != 0 else False

                    if self.msg_err_return:
                        return rtrn_stdout, rtrn_stderr, error

                    return rtrn_stdout, error
                else:
                    stdout = None if not self.silent else su.DEVNULL
                    stderr = None if not self.silent else su.DEVNULL

                    p = su.Popen(
                        cmd, stdout=stdout, stderr=stderr
                    ).communicate()

                    return "", False
            except su.CalledProcessError as err:
                return err.output.decode("utf-8").rstrip(), True
