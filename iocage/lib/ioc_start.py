"""This is responsible for starting jails."""
import re
from datetime import datetime
from os import chdir, getcwd, makedirs, path as ospath, \
    symlink, uname
from shutil import copy
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_call

from iocage.lib.ioc_common import checkoutput, logit, open_atomic
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


class IOCStart(object):
    """
    Starts jails, the network stack for the jail and generates a resolv file
    for them. It also finds any scripts the user supplies for exec_*
    """

    def __init__(self, uuid, jail, path, conf, silent=False, callback=None):
        self.pool = IOCJson(" ").json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.uuid = uuid
        self.jail = jail
        self.path = path
        self.conf = conf
        self.get = IOCJson(self.path, silent=True).json_get_value
        self.set = IOCJson(self.path, silent=True).json_set_value
        self.exec_fib = self.conf["exec_fib"]
        self.callback = callback
        self.silent = silent

        self.__start_jail__()

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
        status, _ = IOCList().list_get_jid(self.uuid)
        userland_version = float(uname()[2].partition("-")[0])

        # If the jail is not running, let's do this thing.
        if not status:
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

            if mount_procfs == "1":
                Popen(["mount", "-t", "procfs", "proc", self.path +
                       "/root/proc"]).communicate()

            try:
                mount_linprocfs = self.conf["mount_linprocfs"]

                if mount_linprocfs == "1":
                    if not ospath.isdir("{}/root/compat/linux/proc".format(
                            self.path)):
                        original_path = getcwd()
                        chdir("{}/root".format(self.path))
                        makedirs("compat/linux/proc", 0o755)
                        chdir(original_path)
                    Popen(["mount", "-t", "linprocfs", "linproc", self.path +
                           "/root/compat/linux/proc"]).communicate()
            except:
                pass

            if self.conf["jail_zfs"] == "on":
                allow_mount = "1"
                enforce_statfs = "1"
                allow_mount_zfs = "1"

                for jdataset in self.conf["jail_zfs_dataset"].split():
                    jdataset = jdataset.strip()

                    try:
                        check_call(["zfs", "get", "-H", "creation",
                                    "{}/{}".format(self.pool,
                                                   jdataset)],
                                   stdout=PIPE, stderr=PIPE)
                    except CalledProcessError:
                        checkoutput(["zfs", "create", "-o",
                                     "compression=lz4", "-o",
                                     "mountpoint=none",
                                     "{}/{}".format(self.pool, jdataset)],
                                    stderr=STDOUT)

                    try:
                        checkoutput(["zfs", "set", "jailed=on",
                                     "{}/{}".format(self.pool, jdataset)],
                                    stderr=STDOUT)
                    except CalledProcessError as err:
                        raise RuntimeError(
                            "{}".format(
                                err.output.decode("utf-8").rstrip()))

            # FreeBSD 9.3 and under do not support this.
            if userland_version <= 9.3:
                tmpfs = ""
                fdescfs = ""
            else:
                tmpfs = "allow.mount.tmpfs={}".format(allow_mount_tmpfs)
                fdescfs = "mount.fdescfs={}".format(mount_fdescfs)

            # FreeBSD 10.3 and under do not support this.
            if userland_version <= 10.3:
                _sysvmsg = ""
                _sysvsem = ""
                _sysvshm = ""
            else:
                _sysvmsg = "sysvmsg={}".format(sysvmsg)
                _sysvsem = "sysvsem={}".format(sysvsem)
                _sysvshm = "sysvshm={}".format(sysvshm)

            if self.conf["vnet"] == "off":
                ip4_addr = self.conf["ip4_addr"]
                ip4_saddrsel = self.conf["ip4_saddrsel"]
                ip4 = self.conf["ip4"]
                ip6_addr = self.conf["ip6_addr"]
                ip6_saddrsel = self.conf["ip6_saddrsel"]
                ip6 = self.conf["ip6"]

                if ip4_addr == "none":
                    ip4_addr = ""

                if ip6_addr == "none":
                    ip6_addr = ""

                net = ["ip4.addr={}".format(ip4_addr),
                       "ip4.saddrsel={}".format(ip4_saddrsel),
                       "ip4={}".format(ip4),
                       "ip6.addr={}".format(ip6_addr),
                       "ip6.saddrsel={}".format(ip6_saddrsel),
                       "ip6={}".format(ip6)]

                vnet = False
            else:
                net = ["vnet"]
                vnet = True

            msg = f"* Starting {self.uuid} ({self.conf['tag']})"
            logit({
                      "level"  : "INFO",
                      "message": msg
                  },
                  _callback=self.callback,
                  silent=self.silent)

            start = Popen([x for x in ["jail", "-c"] + net +
                           ["name=ioc-{}".format(self.uuid),
                            "host.domainname={}".format(host_domainname),
                            "host.hostname={}".format(host_hostname),
                            "path={}/root".format(self.path),
                            "securelevel={}".format(securelevel),
                            "host.hostuuid={}".format(self.uuid),
                            "devfs_ruleset={}".format(devfs_ruleset),
                            "enforce_statfs={}".format(enforce_statfs),
                            "children.max={}".format(children_max),
                            "allow.set_hostname={}".format(allow_set_hostname),
                            "allow.sysvipc={}".format(allow_sysvipc),
                            _sysvmsg,
                            _sysvsem,
                            _sysvshm,
                            "allow.raw_sockets={}".format(allow_raw_sockets),
                            "allow.chflags={}".format(allow_chflags),
                            "allow.mount={}".format(allow_mount),
                            "allow.mount.devfs={}".format(allow_mount_devfs),
                            "allow.mount.nullfs={}".format(allow_mount_nullfs),
                            "allow.mount.procfs={}".format(allow_mount_procfs),
                            tmpfs,
                            "allow.mount.zfs={}".format(allow_mount_zfs),
                            "allow.quotas={}".format(allow_quotas),
                            "allow.socket_af={}".format(allow_socket_af),
                            "exec.prestart={}".format(exec_prestart),
                            "exec.poststart={}".format(exec_poststart),
                            "exec.prestop={}".format(exec_prestop),
                            "exec.stop={}".format(exec_stop),
                            "exec.clean={}".format(exec_clean),
                            "exec.timeout={}".format(exec_timeout),
                            "stop.timeout={}".format(stop_timeout),
                            "mount.fstab={}/fstab".format(self.path),
                            "mount.devfs={}".format(mount_devfs),
                            fdescfs,
                            "allow.dying",
                            "exec.consolelog={}/log/ioc-{}-console.log".format(
                                self.iocroot, self.uuid),
                            "persist"] if x != ''], stdout=PIPE, stderr=PIPE)

            stdout_data, stderr_data = start.communicate()

            if start.returncode:
                # This is actually fatal.
                msg = "  + Start FAILED"
                logit({
                          "level"  : "ERROR",
                          "message": msg
                      },
                      _callback=self.callback,
                      silent=self.silent)

                raise RuntimeError(f"  {stderr_data.decode('utf-8')}")
            else:
                logit({
                          "level"  : "INFO",
                          "message": "  + Started OK"
                      },
                      _callback=self.callback,
                      silent=self.silent)

            os_path = "{}/root/dev/log".format(self.path)
            if not ospath.isfile(os_path) and not ospath.islink(os_path):
                original_path = getcwd()
                chdir("{}/root/dev".format(self.path))
                symlink("../var/run/log", "log")
                chdir(original_path)

            self.start_network(vnet)

            if self.conf["jail_zfs"] == "on":
                for jdataset in self.conf["jail_zfs_dataset"].split():
                    jdataset = jdataset.strip()
                    children = checkoutput(["zfs", "list", "-H", "-r", "-o",
                                            "name", "-S", "name",
                                            "{}/{}".format(self.pool,
                                                           jdataset)])

                    try:
                        checkoutput(
                            ["zfs", "jail", "ioc-{}".format(self.uuid),
                             "{}/{}".format(self.pool, jdataset)],
                            stderr=STDOUT)
                    except CalledProcessError as err:
                        raise RuntimeError(
                            "{}".format(
                                err.output.decode("utf-8").rstrip()))

                    for child in children.split():
                        child = child.strip()

                        try:
                            mountpoint = checkoutput(["zfs", "get", "-H",
                                                      "-o",
                                                      "value", "mountpoint",
                                                      "{}/{}".format(
                                                          self.pool,
                                                          jdataset)]).strip()
                            if mountpoint != "none":
                                checkoutput(["setfib", self.exec_fib, "jexec",
                                             f"ioc-{self.uuid}", "zfs",
                                             "mount", child], stderr=STDOUT)
                        except CalledProcessError as err:
                            raise RuntimeError(
                                "{}".format(
                                    err.output.decode("utf-8").rstrip()))

            self.start_generate_resolv()
            # This needs to be a list.
            exec_start = self.conf["exec_start"].split()

            with open("{}/log/{}-console.log".format(self.iocroot,
                                                     self.uuid), "a") as f:
                services = check_call(["setfib", self.exec_fib, "jexec",
                                       f"ioc-{self.uuid}"] + exec_start,
                                      stdout=f, stderr=PIPE)
            if services:
                msg = "  + Starting services FAILED"
                logit({
                          "level"  : "ERROR",
                          "message": msg
                      },
                      _callback=self.callback,
                      silent=self.silent)
            else:
                msg = "  + Starting services OK"
                logit({
                          "level"  : "INFO",
                          "message": msg
                      },
                      _callback=self.callback,
                      silent=self.silent)

            self.set("last_started={}".format(datetime.utcnow().strftime(
                "%F %T")))
            # TODO: DHCP/BPF
        else:
            msg = f"{self.uuid} ({self.conf['tag']}) is already running!"
            logit({
                      "level"  : "ERROR",
                      "message": msg
                  },
                  _callback=self.callback,
                  silent=self.silent)

    def start_network(self, vnet):
        """
        This function is largely a check to see if VNET is true, and then to
        actually run the correct function, otherwise it passes.

        :param vnet: Boolean
        """
        if vnet:
            _, jid = IOCList().list_get_jid(self.uuid)
            net_configs = ((self.get("ip4_addr"), self.get("defaultrouter")),
                           (self.get("ip6_addr"), self.get("defaultrouter6")))
            nics = self.get("interfaces").split(",")

            for nic in nics:
                self.start_network_interface_vnet(nic, net_configs, jid)

    def start_network_interface_vnet(self, nic, net_configs, jid):
        """
        Start VNET on interface

        :param nic: The network interface to assign the IP in the jail
        :param net_configs: Tuple of IP address and router pairs
        :param jid: The jails ID
        """
        nic, bridge = nic.split(":")

        try:
            membermtu = find_bridge_mtu(bridge)

            ifaces = []
            for addrs, gw in net_configs:
                if addrs != 'none':
                    for addr in addrs.split(','):
                        iface, ip = addr.split("|")
                        if nic != iface:
                            err = f"\n  Invalid interface supplied: {iface}"
                            logit({
                                      "level"  : "ERROR",
                                      "message": f"{err}"
                                  },
                                  _callback=self.callback,
                                  silent=self.silent)

                            err = f"  Did you mean {nic}?\n"
                            logit({
                                      "level"  : "ERROR",
                                      "message": f"{err}"
                                  },
                                  _callback=self.callback,
                                  silent=self.silent)
                            continue
                        if iface not in ifaces:
                            self.start_network_vnet_iface(nic, bridge,
                                                          membermtu, jid)
                            ifaces.append(iface)

                        self.start_network_vnet_addr(iface, ip, gw)

        except CalledProcessError as err:
            logit({
                      "level"  : "WARNING",
                      "message": "Network failed to start:"
                                 f" {err.output.decode('utf-8')}".rstrip()
                  },
                  _callback=self.callback,
                  silent=self.silent)

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
        epair_a = Popen(epair_a_cmd, stdout=PIPE).communicate()[0]
        epair_a = epair_a.strip()
        epair_b = re.sub(b"a$", b"b", epair_a)

        try:
            # Host side
            checkoutput(["ifconfig", epair_a, "name",
                         f"{nic}:{jid}", "mtu", mtu], stderr=STDOUT)
            checkoutput(["ifconfig", f"{nic}:{jid}", "link", mac_a],
                        stderr=STDOUT)
            checkoutput(["ifconfig", f"{nic}:{jid}", "description",
                         "associated with jail:"
                         f" {self.uuid} ({self.conf['tag']})"], stderr=STDOUT)

            # Jail side
            checkoutput(["ifconfig", epair_b, "vnet",
                         f"ioc-{self.uuid}"], stderr=STDOUT)
            checkoutput(["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                         "ifconfig", epair_b, "name", nic, "mtu", mtu],
                        stderr=STDOUT)
            checkoutput(["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                         "ifconfig", nic, "link",mac_b], stderr=STDOUT)
            checkoutput(["ifconfig", bridge, "addm", f"{nic}:{jid}", "up"],
                        stderr=STDOUT)
            checkoutput(["ifconfig", f"{nic}:{jid}", "up"], stderr=STDOUT)
        except CalledProcessError as err:
            return f"{err.output.decode('utf-8')}".rstrip()
        else:
            return

    def start_network_vnet_addr(self, iface, ip, defaultgw):
        """
        Add an IP address to a vnet interface inside the jail.

        :param iface: The interface to use
        :param ip:  The IP address to assign
        :param defaultgw: The gateway IP to assign to the nic
        :return: If an error occurs it returns the error. Otherwise, it's None
        """

        # Crude check to see if it's a IPv6 address
        if ":" in ip:
            ifconfig = [iface, "inet6", ip, "up"]
            route = ["add", "-6", "default", defaultgw]
        else:
            ifconfig = [iface, ip, "up"]
            route = ["add", "default", defaultgw]

        try:
            # Jail side
            checkoutput(["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                         "ifconfig"] + ifconfig, stderr=STDOUT)
            checkoutput(["setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                         "route"] + route, stderr=STDOUT)
        except CalledProcessError as err:
            return f"{err.output.decode('utf-8')}".rstrip()
        else:
            return

    def start_generate_resolv(self):
        resolver = self.get("resolver")
        #                                     compat
        if resolver != "/etc/resolv.conf" and resolver != "none":
            with open_atomic("{}/root/etc/resolv.conf".format(self.path),
                             "w") as resolv_conf:
                for line in resolver.split(";"):
                    resolv_conf.write(line + "\n")
        elif resolver == "none":
            copy("/etc/resolv.conf", "{}/root/etc/resolv.conf".format(
                self.path))
        else:
            copy(resolver, "{}/root/etc/resolv.conf".format(self.path))

    def __start_generate_vnet_mac__(self, nic):
        """
        Generates a random MAC address and checks for uniquness.
        If the jail already has a mac address generated, it will return that
        instead.
        """
        mac = self.get("{}_mac".format(nic))

        if mac == "none":
            jails, paths = IOCList("uuid").list_datasets()
            mac_list = []

            for jail in jails:
                path = paths[jail]
                _conf = IOCJson(path).json_load()
                mac = _conf["mac_prefix"]
                mac_list.append(_conf["{}_mac".format(nic)].split(","))

            # We have to flatten our list of lists.
            mac_list = [m for maclist in mac_list for m in maclist]
            for number in range(16 ** 6):
                # SO
                hex_num_a = hex(number)[2:].zfill(6)
                hex_num_b = hex(number + 1)[2:].zfill(6)
                gen_mac_a = "{}{}{}{}{}{}{}".format(mac, *hex_num_a)
                gen_mac_b = "{}{}{}{}{}{}{}".format(mac, *hex_num_b)
                gen_mac_combined = "{},{}".format(gen_mac_a, gen_mac_b)

                if gen_mac_a in mac_list or gen_mac_b in mac_list:
                    continue
                else:
                    self.set("{}_mac={}".format(nic, gen_mac_combined))
                    return gen_mac_a, gen_mac_b
        else:
            mac_a, mac_b = mac.split(",")
            return mac_a, mac_b


def find_bridge_mtu(bridge):
    memberif = [x for x in
                checkoutput(["ifconfig", bridge]).splitlines()
                if x.strip().startswith("member")]

    if not memberif:
        return '1500'

    membermtu = checkoutput(["ifconfig", memberif[0].split()[1]]).split()
    return membermtu[5]
