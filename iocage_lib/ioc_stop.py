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
import subprocess as su
import netifaces

import iocage_lib.ioc_common
import iocage_lib.ioc_json
import iocage_lib.ioc_list


class IOCStop(object):
    """Stops a jail and unmounts the jails mountpoints."""

    def __init__(self, uuid, path, conf,
                 silent=False, callback=None, force=False):
        self.pool = iocage_lib.ioc_json.IOCJson(" ").json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.uuid = uuid.replace(".", "_")
        self.path = path
        self.conf = conf
        self.force = force
        self.status, self.jid = iocage_lib.ioc_list.IOCList().list_get_jid(
            uuid)
        self.nics = conf["interfaces"]
        self.callback = callback
        self.silent = silent

        self.__stop_jail__()

    def __stop_jail__(self):
        ip4_addr = self.conf["ip4_addr"]
        ip6_addr = self.conf["ip6_addr"]
        vnet = self.conf["vnet"]
        dhcp = self.conf["dhcp"]
        exec_fib = self.conf["exec_fib"]
        devfs_ruleset = self.conf['devfs_ruleset']

        if not self.status:
            msg = f"{self.uuid} is not running!"
            iocage_lib.ioc_common.logit({
                "level": "ERROR",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

            return

        msg = f"* Stopping {self.uuid}"
        iocage_lib.ioc_common.logit({
            "level": "INFO",
            "message": msg
        },
            _callback=self.callback,
            silent=self.silent)

        if not self.force:
            prestop, prestop_err = iocage_lib.ioc_common.runscript(
                self.conf["exec_prestop"])

            if prestop and prestop_err:
                msg = f"  + Running prestop WARNING\n{prestop_err}"
                iocage_lib.ioc_common.logit({
                    "level": "WARNING",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            elif prestop:
                msg = "  + Running prestop OK"
                iocage_lib.ioc_common.logit({
                    "level": "INFO",
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

                iocage_lib.ioc_common.logit({
                    "level": "ERROR",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

            exec_stop = self.conf["exec_stop"].split()
            with open(f"{self.iocroot}/log/{self.uuid}-console.log", "a") as f:
                try:
                    services = su.check_call(["setfib", exec_fib, "jexec",
                                              f"ioc-{self.uuid}"] + exec_stop,
                                             stdout=f, stderr=su.PIPE)
                except su.CalledProcessError as err:
                    services = err.returncode

            if services:
                msg = "  + Stopping services FAILED"
                iocage_lib.ioc_common.logit({
                    "level": "ERROR",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                msg = "  + Stopping services OK"
                iocage_lib.ioc_common.logit({
                    "level": "INFO",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

            if self.conf["jail_zfs"] == "on":
                for jdataset in self.conf["jail_zfs_dataset"].split():
                    jdataset = jdataset.strip()

                    try:
                        children = iocage_lib.ioc_common.checkoutput(
                            ["zfs", "list", "-H", "-r", "-o", "name",
                             "-S", "name",
                             f"{self.pool}/{jdataset}"], stderr=su.STDOUT)

                        for child in children.split():
                            child = child.strip()

                            try:
                                iocage_lib.ioc_common.checkoutput(
                                    ["setfib", exec_fib, "jexec",
                                     f"ioc-{self.uuid}", "zfs", "umount",
                                     child], stderr=su.STDOUT)
                            except su.CalledProcessError as err:
                                mountpoint = iocage_lib.ioc_common.checkoutput(
                                    ["zfs", "get", "-H", "-o", "value",
                                     "mountpoint", f"{self.pool}/{jdataset}"]
                                ).strip()

                                if mountpoint == "none":
                                    pass
                                else:
                                    raise RuntimeError(
                                        "{}".format(
                                            err.output.decode("utf-8").rstrip()
                                        ))

                        try:
                            iocage_lib.ioc_common.checkoutput(
                                ["zfs", "unjail", f"ioc-{self.uuid}",
                                 f"{self.pool}/{jdataset}"], stderr=su.STDOUT)
                        except su.CalledProcessError as err:
                            raise RuntimeError(
                                "{}".format(
                                    err.output.decode("utf-8").rstrip()))

                    except su.CalledProcessError as err:
                        if "dataset does not exist" in \
                                err.output.decode("utf-8"):
                            # There's nothing to do if dataset doesn't exist
                            pass
                        else:
                            raise RuntimeError(
                                "{}".format(
                                    err.output.decode("utf-8").rstrip()))

        # We should still try to destroy the relevant networking
        # related resources if force is true, though we won't raise an exception
        # in that case
        # They haven't set an IP address, this interface won't exist
        destroy_nic = True if dhcp == "on" or ip4_addr != "none" or \
            ip6_addr != "none" else False

        if vnet == "on" and destroy_nic:
            vnet_err = []

            for nic in self.nics.split(","):
                nic = nic.split(":")[0]
                try:
                    iocage_lib.ioc_common.checkoutput(
                        ["ifconfig", f"{nic}:{self.jid}", "destroy"],
                        stderr=su.STDOUT)
                except su.CalledProcessError as err:
                    vnet_err.append(err.output.decode().rstrip())

            if not vnet_err:
                iocage_lib.ioc_common.logit({
                    "level": "INFO",
                    "message": "  + Tearing down VNET OK"
                },
                    _callback=self.callback,
                    silent=self.silent)
            elif vnet_err and not self.force:
                iocage_lib.ioc_common.logit({
                    "level": "INFO",
                    "message": "  + Tearing down VNET FAILED"
                },
                    _callback=self.callback,
                    silent=self.silent)

                for v_err in vnet_err:
                    iocage_lib.ioc_common.logit({
                        "level": "WARNING",
                        "message": f"  {v_err}"
                    },
                        _callback=self.callback,
                        silent=self.silent)

        if ip4_addr != "inherit" and vnet == "off":
            if ip4_addr != "none":
                gws = netifaces.gateways()

                for ip4 in ip4_addr.split(","):
                    # Don't try to remove an alias if there's no interface.

                    if "|" not in ip4:
                        try:
                            def_iface = gws[
                                "default"][netifaces.AF_INET][1]
                            ip4 = f'{def_iface}|{ip4}'
                        except KeyError:
                            # Best effort for default interface
                            continue

                    try:
                        iface, addr = ip4.split("/")[0].split("|")
                        addr = addr.split()
                        iocage_lib.ioc_common.checkoutput(
                            ["ifconfig", iface] + addr +
                            ["-alias"],
                            stderr=su.STDOUT)
                    except su.CalledProcessError as err:
                        if "Can't assign requested address" in \
                                err.output.decode("utf-8"):
                            # They may have a new address that somehow
                            # didn't set correctly. We shouldn't bail on
                            # that.
                            pass
                        elif not self.force:
                            raise RuntimeError(
                                "{}".format(
                                    err.output.decode("utf-8").strip()))

        if ip6_addr != "inherit" and vnet == "off":
            if ip6_addr != "none":
                for ip6 in ip6_addr.split(","):
                    # Don't try to remove an alias if there's no interface.

                    if "|" not in ip6:
                        continue
                    try:
                        iface, addr = ip6.split("/")[0].split("|")
                        addr = addr.split()
                        iocage_lib.ioc_common.checkoutput(
                            ["ifconfig", iface, "inet6"] + addr +
                            ["-alias"], stderr=su.STDOUT)
                    except su.CalledProcessError as err:
                        if "Can't assign requested address" in \
                                err.output.decode("utf-8"):
                            # They may have a new address that somehow
                            # didn't set correctly. We shouldn't bail on
                            # that.
                            pass
                        elif not self.force:
                            raise RuntimeError(
                                "{}".format(
                                    err.output.decode("utf-8").strip()))

        # Clean up after our dynamic devfs rulesets
        ruleset = su.check_output(
            [
                'jls', '-j', f'ioc-{self.uuid}', 'devfs_ruleset'
            ]
        ).decode().rstrip()
        devfs_rulesets = su.run(
            ['devfs', 'rule', 'showsets'],
            stdout=su.PIPE, universal_newlines=True
        )
        ruleset_list = [int(i) for i in devfs_rulesets.stdout.splitlines()]

        # 4 is a placeholder for iocage jails, if the ruleset doesn't exist in
        # ruleset_list, it was generated by iocage as the user supplied a
        # non-existent devfs rule. We still want to clean that up.
        if ruleset != '4' and (devfs_ruleset == '4' or
                               int(devfs_ruleset) not in ruleset_list):
            try:
                su.run(
                    ['devfs', 'rule', '-s', ruleset, 'delset'],
                    stdout=su.PIPE
                )

                msg = f'  + Removing devfs_ruleset: {ruleset} OK'
                iocage_lib.ioc_common.logit({
                    "level": "INFO",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            except su.CalledProcessError as err:
                msg = f'  + Removing devfs_ruleset: {ruleset} FAILED'
                iocage_lib.ioc_common.logit({
                    "level": 'ERROR',
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
        else:
            msg = f'  + Refusing to remove protected devfs_ruleset: {ruleset}'
            iocage_lib.ioc_common.logit({
                "level": 'ERROR',
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

        try:
            stop = su.check_call(["jail", "-r", f"ioc-{self.uuid}"],
                                 stderr=su.PIPE)
        except su.CalledProcessError as err:
            stop = err.returncode

        if stop:
            msg = "  + Removing jail process FAILED"
            iocage_lib.ioc_common.logit({
                "level": "ERROR",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)
        else:
            msg = "  + Removing jail process OK"
            iocage_lib.ioc_common.logit({
                "level": "INFO",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

        poststop, poststop_err = iocage_lib.ioc_common.runscript(
            self.conf["exec_poststop"])

        if poststop and poststop_err:
            msg = f"  + Running poststop WARNING\n{poststop_err}"
            iocage_lib.ioc_common.logit({
                "level": "WARNING",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)
        elif poststop:
            msg = "  + Running poststop OK"
            iocage_lib.ioc_common.logit({
                "level": "INFO",
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

            iocage_lib.ioc_common.logit({
                "level": "ERROR",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

        su.Popen(["umount", "-afF", f"{self.path}/fstab"],
                 stderr=su.PIPE).communicate()
        su.Popen(["umount", "-f", f"{self.path}/root/dev/fd"],
                 stderr=su.PIPE).communicate()
        su.Popen(["umount", "-f", f"{self.path}/root/dev"],
                 stderr=su.PIPE).communicate()
        su.Popen(["umount", "-f", f"{self.path}/root/proc"],
                 stderr=su.PIPE).communicate()
        su.Popen(["umount", "-f", f"{self.path}/root/compat/linux/proc"],
                 stderr=su.PIPE).communicate()
