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
"""This stops jails."""
import os
import subprocess as su

import iocage.lib.ioc_common
import iocage.lib.ioc_json
import iocage.lib.ioc_list


class IOCStop(object):
    """Stops a jail and unmounts the jails mountpoints."""

    def __init__(self, uuid, jail, path, conf, silent=False, callback=None):
        self.pool = iocage.lib.ioc_json.IOCJson(" ").json_get_value("pool")
        self.iocroot = iocage.lib.ioc_json.IOCJson(self.pool).json_get_value(
            "iocroot")
        self.uuid = uuid
        self.jail = jail
        self.path = path
        self.conf = conf
        self.status, self.jid = iocage.lib.ioc_list.IOCList().list_get_jid(
            uuid)
        self.nics = conf["interfaces"]
        self.callback = callback
        self.silent = silent

        self.__stop_jail__()

    def runscript(self, script):
        """
        Runs the users provided script, otherwise returns a tuple with
        True/False and the error.
        """
        if os.access(script, os.X_OK):
            # 0 if success
            try:
                out = iocage.lib.ioc_common.checkoutput(script,
                                                        stderr=su.STDOUT)
            except su.CalledProcessError as err:
                return False, err.output.decode().rstrip("\n")

            if out:
                return True, out.rstrip("\n")

            return True, None
        else:
            return True, "Script is not executable!"

    def __stop_jail__(self):
        ip4_addr = self.conf["ip4_addr"]
        ip6_addr = self.conf["ip6_addr"]
        vnet = self.conf["vnet"]
        exec_fib = self.conf["exec_fib"]

        if not self.status:
            msg = f"{self.uuid} ({self.conf['tag']}) is not running!"
            iocage.lib.ioc_common.logit({
                "level"  : "ERROR",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)
        else:
            msg = f"* Stopping {self.uuid} ({self.conf['tag']})"
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

            prestop, prestop_err = self.runscript(self.conf["exec_prestop"])

            if prestop and prestop_err:
                msg = f"  + Running prestop WARNING\n{prestop_err}"
                iocage.lib.ioc_common.logit({
                    "level"  : "WARNING",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            elif prestop:
                msg = "  + Running prestop OK"
                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                if prestop_err:
                    # They may just be exiting on 1, with no real message.
                    msg = f"  + Running prestop FAILED\n{prestop_err}"
                else:
                    msg = f"  + Running prestop FAILED"

                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

            exec_stop = self.conf["exec_stop"].split()
            with open("{}/log/{}-console.log".format(self.iocroot,
                                                     self.uuid), "a") as f:
                services = su.check_call(["setfib", exec_fib, "jexec",
                                          f"ioc-{self.uuid}"] + exec_stop,
                                         stdout=f, stderr=su.PIPE)
            if services:
                msg = "  + Stopping services FAILED"
                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                msg = "  + Stopping services OK"
                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

            if self.conf["jail_zfs"] == "on":
                for jdataset in self.conf["jail_zfs_dataset"].split():
                    jdataset = jdataset.strip()
                    children = iocage.lib.ioc_common.checkoutput(
                        ["zfs", "list", "-H", "-r", "-o",
                         "name", "-S", "name",
                         "{}/{}".format(self.pool,
                                        jdataset)])

                    for child in children.split():
                        child = child.strip()

                        try:
                            iocage.lib.ioc_common.checkoutput(
                                ["setfib", exec_fib, "jexec",
                                 f"ioc-{self.uuid}", "zfs", "umount",
                                 child], stderr=su.STDOUT)
                        except su.CalledProcessError as err:
                            mountpoint = iocage.lib.ioc_common.checkoutput(
                                ["zfs", "get", "-H",
                                 "-o",
                                 "value", "mountpoint",
                                 "{}/{}".format(
                                     self.pool,
                                     jdataset)]).strip()
                            if mountpoint == "none":
                                pass
                            else:
                                raise RuntimeError(
                                    "{}".format(
                                        err.output.decode("utf-8").rstrip()))

                    try:
                        iocage.lib.ioc_common.checkoutput(
                            ["zfs", "unjail", "ioc-{}".format(
                                self.uuid),
                             "{}/{}".format(self.pool, jdataset)],
                            stderr=su.STDOUT)
                    except su.CalledProcessError as err:
                        raise RuntimeError(
                            "{}".format(
                                err.output.decode("utf-8").rstrip()))

            if vnet == "on":
                for nic in self.nics.split(","):
                    nic = nic.split(":")[0]
                    try:
                        iocage.lib.ioc_common.checkoutput(
                            ["ifconfig", "{}:{}".format(nic, self.jid),
                             "destroy"], stderr=su.STDOUT)
                    except su.CalledProcessError:
                        pass

            if ip4_addr != "inherit" and vnet == "off":
                if ip4_addr != "none":
                    for ip4 in ip4_addr.split(","):
                        try:
                            iface, addr = ip4.split("/")[0].split("|")
                            addr = addr.split()
                            iocage.lib.ioc_common.checkoutput(
                                ["ifconfig", iface] + addr +
                                ["-alias"],
                                stderr=su.STDOUT)
                        except ValueError:
                            # Likely a misconfigured ip_addr with no interface.
                            msg = "  ! IP4 address is missing an interface," \
                                  " set ip4_addr to \"INTERFACE|IPADDR\""
                            iocage.lib.ioc_common.logit({
                                "level"  : "INFO",
                                "message": msg
                            },
                                _callback=self.callback,
                                silent=self.silent)
                        except su.CalledProcessError as err:
                            if "Can't assign requested address" in \
                                    err.output.decode("utf-8"):
                                # They may have a new address that somehow
                                # didn't set correctly. We shouldn't bail on
                                # that.
                                pass
                            else:
                                raise RuntimeError(
                                    "{}".format(
                                        err.output.decode("utf-8").strip()))

            if ip6_addr != "inherit" and vnet == "off":
                if ip6_addr != "none":
                    for ip6 in ip6_addr.split(","):
                        try:
                            iface, addr = ip6.split("/")[0].split("|")
                            addr = addr.split()
                            iocage.lib.ioc_common.checkoutput(
                                ["ifconfig", iface, "inet6"] + addr +
                                ["-alias"], stderr=su.STDOUT)
                        except ValueError:
                            # Likely a misconfigured ip_addr with no interface.
                            msg = "  ! IP6 address is missing an interface," \
                                  " set ip6_addr to \"INTERFACE|IPADDR\""
                            iocage.lib.ioc_common.logit({
                                "level"  : "INFO",
                                "message": msg
                            },
                                _callback=self.callback,
                                silent=self.silent)
                        except su.CalledProcessError as err:
                            if "Can't assign requested address" in \
                                    err.output.decode("utf-8"):
                                # They may have a new address that somehow
                                # didn't set correctly. We shouldn't bail on
                                # that.
                                pass
                            else:
                                raise RuntimeError(
                                    "{}".format(
                                        err.output.decode("utf-8").strip()))

            stop = su.check_call(["jail", "-r", "ioc-{}".format(self.uuid)],
                                 stderr=su.PIPE)

            if stop:
                msg = "  + Removing jail process FAILED"
                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                msg = "  + Removing jail process OK"
                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

            poststop, poststop_err = self.runscript(self.conf["exec_poststop"])

            if poststop and poststop_err:
                msg = f"  + Running poststop WARNING\n{poststop_err}"
                iocage.lib.ioc_common.logit({
                    "level"  : "WARNING",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            elif poststop:
                msg = "  + Running poststop OK"
                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                if poststop_err:
                    # They may just be exiting on 1, with no real message.
                    msg = f"  + Running poststop FAILED\n{poststop_err}"
                else:
                    msg = f"  + Running poststop FAILED"

                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

            su.Popen(["umount", "-afF", "{}/fstab".format(self.path)],
                     stderr=su.PIPE).communicate()
            su.Popen(["umount", "-f", "{}/root/dev/fd".format(self.path)],
                     stderr=su.PIPE).communicate()
            su.Popen(["umount", "-f", "{}/root/dev".format(self.path)],
                     stderr=su.PIPE).communicate()
            su.Popen(["umount", "-f", "{}/root/proc".format(self.path)],
                     stderr=su.PIPE).communicate()
            su.Popen(
                ["umount", "-f",
                 "{}/root/compat/linux/proc".format(self.path)],
                stderr=su.PIPE).communicate()
