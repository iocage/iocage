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
"""This is responsible for starting jails."""
import datetime
import hashlib
import os
import re
import shutil
import subprocess as su

import iocage.lib.ioc_common
import iocage.lib.ioc_json
import iocage.lib.ioc_list


class IOCStart(object):
    """
    Starts jails, the network stack for the jail and generates a resolv file
    for them. It also finds any scripts the user supplies for exec_*
    """

    def __init__(self, uuid, path, conf, exit_on_error=False, silent=False,
                 callback=None):
        self.uuid = uuid.replace(".", "_")
        self.path = path
        self.conf = conf
        self.exit_on_error = exit_on_error
        self.callback = callback
        self.silent = silent

        try:
            self.pool = iocage.lib.ioc_json.IOCJson(" ").json_get_value("pool")
            self.iocroot = iocage.lib.ioc_json.IOCJson(
                self.pool).json_get_value("iocroot")
            self.get = iocage.lib.ioc_json.IOCJson(self.path,
                                                   silent=True).json_get_value
            self.set = iocage.lib.ioc_json.IOCJson(self.path,
                                                   silent=True).json_set_value
            self.exec_fib = self.conf["exec_fib"]
            self.__start_jail__()
        except TypeError:
            # Bridge MTU unit tests will not have these
            # TODO: Something less terrible
            pass

    def __start_jail__(self):
        """
        Takes a UUID, and the user supplied name of a jail, the path and the
        configuration location. It then supplies the jail utility with that
        information in a format it can parse.

        start_jail also checks if the jail is already running, if the
        user wished for procfs or linprocfs to be mounted, and the user's
        specified data that is meant to populate resolv.conf
        will be copied into the jail.
        """
        status, _ = iocage.lib.ioc_list.IOCList().list_get_jid(self.uuid)
        userland_version = float(os.uname()[2].partition("-")[0])

        # If the jail is not running, let's do this thing.
        if status:
            msg = f"{self.uuid} is already running!"
            iocage.lib.ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": msg
            }, exit_on_error=self.exit_on_error, _callback=self.callback,
                silent=self.silent)

        mount_procfs = self.conf["mount_procfs"]
        host_domainname = self.conf["host_domainname"]
        host_hostname = self.conf["host_hostname"]
        securelevel = self.conf["securelevel"]
        devfs_ruleset = self.conf["devfs_ruleset"]
        enforce_statfs = self.conf["enforce_statfs"]
        children_max = self.conf["children_max"]
        allow_set_hostname = self.conf["allow_set_hostname"]
        allow_sysvipc = self.conf["allow_sysvipc"]
        allow_raw_sockets = self.conf["allow_raw_sockets"]
        allow_chflags = self.conf["allow_chflags"]
        allow_mount = self.conf["allow_mount"]
        allow_mount_devfs = self.conf["allow_mount_devfs"]
        allow_mount_nullfs = self.conf["allow_mount_nullfs"]
        allow_mount_procfs = self.conf["allow_mount_procfs"]
        allow_mount_tmpfs = self.conf["allow_mount_tmpfs"]
        allow_mount_zfs = self.conf["allow_mount_zfs"]
        allow_quotas = self.conf["allow_quotas"]
        allow_socket_af = self.conf["allow_socket_af"]
        exec_prestart = self.conf["exec_prestart"]
        exec_poststart = self.conf["exec_poststart"]
        exec_prestop = self.conf["exec_prestop"]
        exec_stop = self.conf["exec_stop"]
        exec_clean = self.conf["exec_clean"]
        exec_timeout = self.conf["exec_timeout"]
        stop_timeout = self.conf["stop_timeout"]
        mount_devfs = self.conf["mount_devfs"]
        mount_fdescfs = self.conf["mount_fdescfs"]
        sysvmsg = self.conf["sysvmsg"]
        sysvsem = self.conf["sysvsem"]
        sysvshm = self.conf["sysvshm"]
        bpf = self.conf["bpf"]
        dhcp = self.conf["dhcp"]
        prop_missing = False

        if dhcp == "on":
            if bpf != "yes":
                msg = f"{self.uuid} requires bpf=yes!"
                prop_missing = True
            elif self.conf["vnet"] != "on":
                # We are already setting a vnet variable below.
                msg = f"{self.uuid} requires vnet=on!"
                prop_missing = True

            if prop_missing:
                iocage.lib.ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": msg
                }, exit_on_error=self.exit_on_error, _callback=self.callback,
                    silent=self.silent)

            self.__check_dhcp__()
            devfs_ruleset = "5" if devfs_ruleset == "4" else devfs_ruleset

        if mount_procfs == "1":
            su.Popen(["mount", "-t", "procfs", "proc", self.path +
                      "/root/proc"]).communicate()

        try:
            mount_linprocfs = self.conf["mount_linprocfs"]

            if mount_linprocfs == "1":
                if not os.path.isdir(f"{self.path}/root/compat/linux/proc"):
                    original_path = os.getcwd()
                    os.chdir(f"{self.path}/root")
                    os.makedirs("compat/linux/proc", 0o755)
                    os.chdir(original_path)
                su.Popen(
                    ["mount", "-t", "linprocfs", "linproc", self.path +
                     "/root/compat/linux/proc"]).communicate()
        except:
            pass

        if self.conf["jail_zfs"] == "on":
            allow_mount = "1"
            enforce_statfs = enforce_statfs if enforce_statfs != "2" \
                else "1"
            allow_mount_zfs = "1"

            for jdataset in self.conf["jail_zfs_dataset"].split():
                jdataset = jdataset.strip()

                try:
                    su.check_call(["zfs", "get", "-H", "creation",
                                   f"{self.pool}/{jdataset}"],
                                  stdout=su.PIPE, stderr=su.PIPE)
                except su.CalledProcessError:
                    iocage.lib.ioc_common.checkoutput(
                        ["zfs", "create", "-o",
                         "compression=lz4", "-o",
                         "mountpoint=none",
                         f"{self.pool}/{jdataset}"],
                        stderr=su.STDOUT)

                try:
                    iocage.lib.ioc_common.checkoutput(
                        ["zfs", "set", "jailed=on",
                         f"{self.pool}/{jdataset}"],
                        stderr=su.STDOUT)
                except su.CalledProcessError as err:
                    raise RuntimeError(
                        f"{err.output.decode('utf-8').rstrip()}")

        # FreeBSD 9.3 and under do not support this.
        if userland_version <= 9.3:
            tmpfs = ""
            fdescfs = ""
        else:
            tmpfs = f"allow.mount.tmpfs={allow_mount_tmpfs}"
            fdescfs = f"mount.fdescfs={mount_fdescfs}"

        # FreeBSD 10.3 and under do not support this.
        if userland_version <= 10.3:
            _sysvmsg = ""
            _sysvsem = ""
            _sysvshm = ""
        else:
            _sysvmsg = f"sysvmsg={sysvmsg}"
            _sysvsem = f"sysvsem={sysvsem}"
            _sysvshm = f"sysvshm={sysvshm}"

        if self.conf["vnet"] == "off":
            ip4_addr = self.conf["ip4_addr"]
            ip4_saddrsel = self.conf["ip4_saddrsel"]
            ip4 = self.conf["ip4"]
            ip6_addr = self.conf["ip6_addr"]
            ip6_saddrsel = self.conf["ip6_saddrsel"]
            ip6 = self.conf["ip6"]
            net = []

            if ip4_addr != "none":
                net.append(f"ip4.addr={ip4_addr}")

            if ip6_addr != "none":
                net.append(f"ip6.addr={ip6_addr}")

            net += [f"ip4.saddrsel={ip4_saddrsel}",
                    f"ip4={ip4}",
                    f"ip6.saddrsel={ip6_saddrsel}",
                    f"ip6={ip6}"]

            vnet = False
        else:
            net = ["vnet"]
            vnet = True

        if bpf == "yes":
            self.__generate_bpf_ruleset()

        msg = f"* Starting {self.uuid}"
        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": msg
        },
            _callback=self.callback,
            silent=self.silent)

        if devfs_ruleset != "5" and dhcp == "on":
            iocage.lib.ioc_common.logit({
                "level"  : "WARNING",
                "message": "  You are not using the iocage devfs_ruleset"
                           " of 5, DHCP may not work."
            },
                _callback=self.callback,
                silent=self.silent)

        start = su.Popen([x for x in ["jail", "-c"] + net +
                          [f"name=ioc-{self.uuid}",
                           f"host.domainname={host_domainname}",
                           f"host.hostname={host_hostname}",
                           f"path={self.path}/root",
                           f"securelevel={securelevel}",
                           f"host.hostuuid={self.uuid}",
                           f"devfs_ruleset={devfs_ruleset}",
                           f"enforce_statfs={enforce_statfs}",
                           f"children.max={children_max}",
                           f"allow.set_hostname={allow_set_hostname}",
                           f"allow.sysvipc={allow_sysvipc}",
                           _sysvmsg,
                           _sysvsem,
                           _sysvshm,
                           f"allow.raw_sockets={allow_raw_sockets}",
                           f"allow.chflags={allow_chflags}",
                           f"allow.mount={allow_mount}",
                           f"allow.mount.devfs={allow_mount_devfs}",
                           f"allow.mount.nullfs={allow_mount_nullfs}",
                           f"allow.mount.procfs={allow_mount_procfs}",
                           tmpfs,
                           f"allow.mount.zfs={allow_mount_zfs}",
                           f"allow.quotas={allow_quotas}",
                           f"allow.socket_af={allow_socket_af}",
                           f"exec.prestart={exec_prestart}",
                           f"exec.poststart={exec_poststart}",
                           f"exec.prestop={exec_prestop}",
                           f"exec.stop={exec_stop}",
                           f"exec.clean={exec_clean}",
                           f"exec.timeout={exec_timeout}",
                           f"stop.timeout={stop_timeout}",
                           f"mount.fstab={self.path}/fstab",
                           f"mount.devfs={mount_devfs}",
                           fdescfs,
                           "allow.dying",
                           f"exec.consolelog={self.iocroot}/log/ioc-"
                           f"{self.uuid}-console.log",
                           "persist"] if x != ''], stdout=su.PIPE,
                         stderr=su.PIPE)

        stdout_data, stderr_data = start.communicate()

        if start.returncode:
            # This is actually fatal.
            msg = "  + Start FAILED"
            iocage.lib.ioc_common.logit({
                "level"  : "ERROR",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

            iocage.lib.ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": stderr_data.decode('utf-8')
            }, exit_on_error=self.exit_on_error, _callback=self.callback,
                silent=self.silent)
        else:
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": "  + Started OK"
            },
                _callback=self.callback,
                silent=self.silent)

        os_path = f"{self.path}/root/dev/log"
        if not os.path.isfile(os_path) and not os.path.islink(os_path):
            original_path = os.getcwd()
            os.chdir(f"{self.path}/root/dev")
            os.symlink("../var/run/log", "log")
            os.chdir(original_path)

        vnet_err = self.start_network(vnet)

        if not vnet_err and vnet:
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": "  + Configuring VNET OK"
            },
                _callback=self.callback,
                silent=self.silent)
        elif vnet_err and vnet:
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": "  + Configuring VNET FAILED"
            },
                _callback=self.callback,
                silent=self.silent)

            for v_err in vnet_err:
                iocage.lib.ioc_common.logit({
                    "level"  : "WARNING",
                    "message": f"  {v_err}"
                },
                    _callback=self.callback,
                    silent=self.silent)

        if self.conf["jail_zfs"] == "on":
            for jdataset in self.conf["jail_zfs_dataset"].split():
                jdataset = jdataset.strip()
                children = iocage.lib.ioc_common.checkoutput(
                    ["zfs", "list", "-H", "-r", "-o",
                     "name", "-S", "name",
                     f"{self.pool}/{jdataset}"])

                try:
                    iocage.lib.ioc_common.checkoutput(
                        ["zfs", "jail", "ioc-{}".format(self.uuid),
                         "{}/{}".format(self.pool, jdataset)],
                        stderr=su.STDOUT)
                except su.CalledProcessError as err:
                    raise RuntimeError(
                        f"{err.output.decode('utf-8').rstrip()}")

                for child in children.split():
                    child = child.strip()

                    try:
                        mountpoint = iocage.lib.ioc_common.checkoutput(
                            ["zfs", "get", "-H",
                             "-o",
                             "value", "mountpoint",
                             f"{self.pool}/{jdataset}"]).strip()
                        if mountpoint != "none":
                            iocage.lib.ioc_common.checkoutput(
                                ["setfib", self.exec_fib, "jexec",
                                 f"ioc-{self.uuid}", "zfs",
                                 "mount", child], stderr=su.STDOUT)
                    except su.CalledProcessError as err:
                        msg = err.output.decode('utf-8').rstrip()
                        iocage.lib.ioc_common.logit({
                            "level"  : "EXCEPTION",
                            "message": msg
                        }, exit_on_error=self.exit_on_error,
                            _callback=self.callback,
                            silent=self.silent)

        self.start_generate_resolv()
        self.start_copy_localtime()
        # This needs to be a list.
        exec_start = self.conf["exec_start"].split()

        with open("{}/log/{}-console.log".format(self.iocroot,
                                                 self.uuid), "a") as f:
            services = su.check_call(["setfib", self.exec_fib, "jexec",
                                      f"ioc-{self.uuid}"] + exec_start,
                                     stdout=f, stderr=su.PIPE)
        if services:
            msg = "  + Starting services FAILED"
            iocage.lib.ioc_common.logit({
                "level"  : "ERROR",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)
        else:
            msg = "  + Starting services OK"
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

        self.set(
            "last_started={}".format(datetime.datetime.utcnow().strftime(
                "%F %T")))

    def start_network(self, vnet):
        """
        This function is largely a check to see if VNET is true, and then to
        actually run the correct function, otherwise it passes.

        :param vnet: Boolean
        """
        errors = []

        if not vnet:
            return

        _, jid = iocage.lib.ioc_list.IOCList().list_get_jid(self.uuid)
        net_configs = (
            (self.get("ip4_addr"), self.get("defaultrouter"), False),
            (self.get("ip6_addr"), self.get("defaultrouter6"), True))
        nics = self.get("interfaces").split(",")

        for nic in nics:
            err = self.start_network_interface_vnet(nic, net_configs, jid)

            if err:
                errors.append(err)

        if len(errors) != 0:
            return errors

    def start_network_interface_vnet(self, nic_defs, net_configs, jid):
        """
        Start VNET on interface

        :param nic_defs: comma separated interface definitions (nic, bridge)
        :param net_configs: Tuple of IP address and router pairs
        :param jid: The jails ID
        """
        nic_defs = nic_defs.split(",")
        nics = list(map(lambda x: x.split(":")[0], nic_defs))

        for nic_def in nic_defs:

            nic, bridge = nic_def.split(":")

            try:
                membermtu = self.find_bridge_mtu(bridge)
                dhcp = self.get("dhcp")

                ifaces = []
                for addrs, gw, ipv6 in net_configs:
                    if dhcp == "on":
                        # Spoofing IP address, it doesn't matter with DHCP
                        addrs = f"{nic}|''"

                    if addrs == 'none':
                        continue

                    for addr in addrs.split(','):
                        iface, ip = addr.split("|")
                        if iface not in nics:
                            continue

                        if iface not in ifaces:
                            self.start_network_vnet_iface(nic, bridge,
                                                          membermtu, jid)
                            ifaces.append(iface)

                        self.start_network_vnet_addr(iface, ip, gw, ipv6)

            except su.CalledProcessError as err:
                return err.output.decode("utf-8").rstrip()

    def start_network_vnet_iface(self, nic, bridge, mtu, jid):
        """
        The real meat and potatoes for starting a VNET interface.

        :param nic: The network interface to assign the IP in the jail
        :param bridge: The bridge to attach the VNET interface
        :param mtu: The mtu of the VNET interface
        :param jid: The jails ID
        :return: If an error occurs it returns the error. Otherwise, it's None
        """

        mac_a, mac_b = self.__start_generate_vnet_mac__(nic)
        epair_a_cmd = ["ifconfig", "epair", "create"]
        epair_a = su.Popen(epair_a_cmd, stdout=su.PIPE).communicate()[0]
        epair_a = epair_a.strip()
        epair_b = re.sub(b"a$", b"b", epair_a)

        try:
            # Host side
            iocage.lib.ioc_common.checkoutput(["ifconfig", epair_a, "name",
                                               f"{nic}:{jid}", "mtu", mtu],
                                              stderr=su.STDOUT)
            iocage.lib.ioc_common.checkoutput(
                ["ifconfig", f"{nic}:{jid}", "link", mac_a],
                stderr=su.STDOUT)
            iocage.lib.ioc_common.checkoutput(
                ["ifconfig", f"{nic}:{jid}", "description",
                 "associated with jail:"
                 f" {self.uuid}"],
                stderr=su.STDOUT)

            # Jail side
            iocage.lib.ioc_common.checkoutput(["ifconfig", epair_b, "vnet",
                                               f"ioc-{self.uuid}"],
                                              stderr=su.STDOUT)
            iocage.lib.ioc_common.checkoutput(
                ["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                 "ifconfig", epair_b, "name", nic, "mtu", mtu],
                stderr=su.STDOUT)
            iocage.lib.ioc_common.checkoutput(
                ["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",

                 "ifconfig", nic, "link", mac_b], stderr=su.STDOUT)
            iocage.lib.ioc_common.checkoutput(
                ["ifconfig", bridge, "addm", f"{nic}:{jid}", "up"],
                stderr=su.STDOUT)
            iocage.lib.ioc_common.checkoutput(
                ["ifconfig", f"{nic}:{jid}", "up"],
                stderr=su.STDOUT)
        except su.CalledProcessError as err:
            return f"{err.output.decode('utf-8')}".rstrip()
        else:
            return

    def start_network_vnet_addr(self, iface, ip, defaultgw, ipv6=False):
        """
        Add an IP address to a vnet interface inside the jail.

        :param iface: The interface to use
        :param ip:  The IP address to assign
        :param defaultgw: The gateway IP to assign to the nic
        :return: If an error occurs it returns the error. Otherwise, it's None
        """
        dhcp = self.get("dhcp")

        # Crude check to see if it's a IPv6 address
        if ipv6:
            ifconfig = [iface, "inet6", ip, "up"]
            route = ["add", "-6", "default", defaultgw]
        else:
            ifconfig = [iface, ip, "up"]
            route = ["add", "default", defaultgw]

        try:
            if dhcp == "off":
                # Jail side
                iocage.lib.ioc_common.checkoutput(
                    ["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                     "ifconfig"] + ifconfig, stderr=su.STDOUT)
                iocage.lib.ioc_common.checkoutput(
                    ["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                     "route"] + route, stderr=su.STDOUT)
            else:
                if ipv6:
                    # Requires either rtsol or ISC dhclient, the user likely
                    #  knows which they want, DHCP is for IP4 in iocage.
                    return

                iocage.lib.ioc_common.checkoutput(
                    ["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                     "service", "dhclient", "start", iface],
                    stderr=su.STDOUT)
        except su.CalledProcessError as err:
            return f"{err.output.decode('utf-8')}".rstrip()
        else:
            return

    def start_copy_localtime(self):
        host_time = self.get("host_time")
        file = f"{self.path}/root/etc/localtime"
        if host_time != "yes":
            return

        if os.path.isfile(file):
            os.remove(file)

        try:
            shutil.copy("/etc/localtime", file, follow_symlinks=False)
        except FileNotFoundError:
            return

    def start_generate_resolv(self):
        resolver = self.get("resolver")
        #                                     compat
        if resolver != "/etc/resolv.conf" and resolver != "none" and \
                        resolver != "/dev/null":
            with iocage.lib.ioc_common.open_atomic(
                    f"{self.path}/root/etc/resolv.conf", "w") as resolv_conf:
                for line in resolver.split(";"):
                    resolv_conf.write(line + "\n")
        elif resolver == "none":
            shutil.copy("/etc/resolv.conf",
                        f"{self.path}/root/etc/resolv.conf")
        elif resolver == "/dev/null":
            # They don't want the resolv.conf to be touched.
            return
        else:
            shutil.copy(resolver, f"{self.path}/root/etc/resolv.conf")

    def __generate_mac_bytes(self, nic):
        m = hashlib.md5()
        m.update(self.uuid.encode("utf-8"))
        m.update(nic.encode("utf-8"))
        prefix = self.get("mac_prefix")
        return f"{prefix}{m.hexdigest()[0:12-len(prefix)]}"

    def __generate_mac_address_pair(self, nic):
        mac_a = self.__generate_mac_bytes(nic)
        mac_b = hex(int(mac_a, 16) + 1)[2:].zfill(12)
        return mac_a, mac_b

    def __start_generate_vnet_mac__(self, nic):
        """
        Generates a random MAC address and checks for uniquness.
        If the jail already has a mac address generated, it will return that
        instead.
        """
        mac = self.get("{}_mac".format(nic))

        if mac == "none":
            mac_a, mac_b = self.__generate_mac_address_pair(nic)
            self.set(f"{nic}_mac={mac_a},{mac_b}")
        else:
            mac_a, mac_b = mac.split(",")

        return mac_a, mac_b

    @staticmethod
    def __generate_bpf_ruleset():
        """
        Will add the bpf ruleset to the hosts /etc/devfs.rules if it doesn't
        exist, otherwise it will do nothing.
        """
        devfs_cmd = ["service", "devfs", "restart"]
        bpf_ruleset = """
## IOCAGE -- Add DHCP to ruleset 4
[devfsrules_jail_dhcp=5]
add include $devfsrules_hide_all
add include $devfsrules_unhide_basic
add include $devfsrules_unhide_login
add path zfs unhide
add path 'bpf*' unhide
"""
        with open("/etc/devfs.rules", "a+") as devfs:
            devfs.seek(0, 0)

            for line in devfs:
                if "## IOCAGE -- Add DHCP to ruleset 4" in line:
                    break
            else:
                # Not found, else is ran if break statement isn't executed
                devfs.write(bpf_ruleset)
                su.check_call(devfs_cmd, stdout=su.PIPE, stderr=su.PIPE)

    def __check_dhcp__(self):
        nic_list = self.get("interfaces").split(",")
        nics = list(map(lambda x: x.split(":")[0], nic_list))
        _rc = open(f"{self.path}/root/etc/rc.conf").readlines()

        for nic in nics:
            replaced = False

            for no, line in enumerate(_rc):
                if f"ifconfig_{nic}" in line:
                    _rc[no] = f'ifconfig_{nic}="DHCP"\n'
                    replaced = True

            if not replaced:
                # They didn't have any interface in their rc.conf,
                # fresh jail perhaps?
                _rc.insert(0, f'ifconfig_{nic}="DHCP"\n')

            with open(f"{self.path}/root/etc/rc.conf", "w") as rc:
                for line in _rc:
                    rc.write(line)

    def find_bridge_mtu(self, bridge):
        try:
            dhcp = self.get("dhcp")
        except:
            # To spoof unit test.
            dhcp = "off"

        try:
            if dhcp == "on":
                default_iface_cmd = ["netstat", "-f", "inet", "-nrW"]
                default_iface = su.check_output(default_iface_cmd)
                default_if = ""

                for line in default_iface.splitlines():
                    if b"default" in line:
                        default_if = line.split()[5].decode()

                bridge_cmd = ["ifconfig", bridge, "create", "addm",
                              default_if]
            else:
                bridge_cmd = ["ifconfig", bridge, "create", "addm"]

            su.check_call(bridge_cmd, stdout=su.PIPE, stderr=su.PIPE)
        except su.CalledProcessError:
            # The bridge already exists, this is just best effort.
            pass

        memberif = [x for x in
                    iocage.lib.ioc_common.checkoutput(
                        ["ifconfig", bridge]).splitlines()
                    if x.strip().startswith("member")]

        if not memberif:
            return '1500'

        membermtu = iocage.lib.ioc_common.checkoutput(
            ["ifconfig", memberif[0].split()[1]]).split()
        return membermtu[5]
