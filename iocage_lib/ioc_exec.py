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
import iocage_lib.ioc_exceptions
import select
import fcntl
import os


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
                 su_env=None,
                 callback=None):
        self.command = command
        self.uuid = uuid.replace(".", "_") if uuid is not None else uuid
        self.path = path
        self.host_user = host_user
        self.jail_user = jail_user
        self.plugin = plugin
        self.pkg = pkg
        self.skip = skip
        self.silent = silent
        self.msg_return = msg_return
        self.msg_err_return = msg_err_return

        path = '/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:'\
               '/usr/local/bin:/root/bin'
        su_env = su_env or {}
        su_env.setdefault('PATH', path)
        su_env.setdefault('PWD', '/')
        su_env.setdefault('HOME', '/')

        self.su_env = su_env
        self.callback = callback

    def exec_jail(self):
        if self.jail_user:
            flag = "-U"
            user = self.jail_user
        else:
            flag = "-u"
            user = self.host_user

        if self.uuid is not None:
            status, _ = iocage_lib.ioc_list.IOCList().list_get_jid(self.uuid)
            conf = iocage_lib.ioc_json.IOCJson(self.path).json_load()
            exec_fib = conf["exec_fib"]

            if not status:
                if not self.plugin and not self.skip:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"{self.uuid} is not running,"
                            " starting jail"
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

        try:
            if not self.pkg:
                cmd = [
                    "/usr/sbin/setfib", exec_fib, "jexec", flag, user,
                    f"ioc-{self.uuid}"
                ] + list(self.command)
            else:
                cmd = self.command

            if self.msg_return or self.msg_err_return:
                p = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE,
                             close_fds=True, bufsize=0, env=self.su_env)

                # Courtesy of @william-gr
                # service(8) and some rc.d scripts have the bad habit of
                # exec'ing and never closing stdout/stderr. This makes
                # sure we read only enough until the command exits and do
                # not wait on the pipe to close on the other end.
                #
                # Same issue can be demonstrated with:
                # $ jexec 1 service postgresql onerestart | cat
                # ... <hangs>
                # postgresql rc.d command never closes the pipe
                rtrn_stdout = b''
                rtrn_stderr = b''
                for i in ('stdout', 'stderr'):
                    fileno = getattr(p, i).fileno()
                    fl = fcntl.fcntl(fileno, fcntl.F_GETFL)
                    fcntl.fcntl(fileno, fcntl.F_SETFL, fl | os.O_NONBLOCK)

                timeout = 0.1
                yield_stdout_now = False
                yield_stderr_now = False

                while True:
                    r = select.select([
                        p.stdout.fileno(),
                        p.stderr.fileno()], [], [], timeout)[0]

                    if p.poll() is not None:
                        if timeout == 0:
                            break
                        else:
                            timeout = 0

                    if r:
                        if p.stdout.fileno() in r:
                            if rtrn_stdout.endswith(b'\n'):
                                yield_stdout_now = True

                            if not yield_stdout_now:
                                stdout = p.stdout.read()
                                rtrn_stdout += stdout

                                if rtrn_stdout.endswith(b'\n'):
                                    yield_stdout_now = True

                        if p.stderr.fileno() in r:
                            if rtrn_stderr.endswith(b'\n'):
                                yield_stderr_now = True

                            if not yield_stderr_now:
                                stderr = p.stderr.read()
                                rtrn_stderr += stderr

                                if rtrn_stderr.endswith(b'\n'):
                                    yield_stderr_now = True

                        if self.msg_err_return:
                            if yield_stdout_now and yield_stderr_now:
                                yield_stdout_now = yield_stderr_now = False
                                _rtrn_stdout = rtrn_stdout
                                _rtrn_stderr = rtrn_stderr

                                # Set up a new line
                                rtrn_stdout = rtrn_stderr = b''

                                yield _rtrn_stdout, _rtrn_stderr
                        else:
                            if yield_stdout_now:
                                yield_stdout_now = False
                                _rtrn_stdout = rtrn_stdout

                                # Set up a new line
                                rtrn_stdout = b''

                                yield _rtrn_stdout

                p.stdout.close()
                p.stderr.close()

                error = True if p.returncode != 0 else False

                if error and self.uuid is not None:
                    # self.uuid being None means a release being updated,
                    # We will get false positives for EOL notices
                    raise iocage_lib.ioc_exceptions.CommandFailed(
                        rtrn_stderr)
            else:
                stdout = None if not self.silent else su.DEVNULL
                stderr = None if not self.silent else su.DEVNULL

                p = su.Popen(
                    cmd, stdout=stdout, stderr=stderr, env=self.su_env
                ).communicate()

                return "", False
        except su.CalledProcessError as err:
            return err.output.decode("utf-8").rstrip(), True
