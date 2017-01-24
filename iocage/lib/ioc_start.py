"""This is responsible for starting jails."""
import logging
from datetime import datetime
from shutil import copy
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_call, \
    check_output

import re
from os import X_OK, access, chdir, getcwd, makedirs, path as ospath, symlink, \
    uname

from iocage.lib.ioc_common import open_atomic
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


class IOCStart(object):
    """
    Starts jails, the network stack for the jail and generates a resolv file
    for them. It also finds any scripts the user supplies for exec_*
    """

    def __init__(self, uuid, jail, path, conf, silent=False):
        self.pool = IOCJson(" ").get_prop_value("pool")
        self.iocroot = IOCJson(self.pool).get_prop_value("iocroot")
        self.uuid = uuid
        self.jail = jail
        self.path = path
        self.conf = conf
        self.get = IOCJson(self.path, silent=True).get_prop_value
        self.set = IOCJson(self.path, silent=True).set_prop_value
        self.lgr = logging.getLogger('ioc_start')

        if silent:
            self.lgr.disabled = True

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
        status, _ = IOCList().get_jid(self.uuid)
        userland_version = float(uname()[2][:4])

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
            exec_prestart = self.findscript("prestart")
            exec_poststart = self.findscript("poststart")
            exec_prestop = self.findscript("prestop")
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
                        makedirs("compat/linux/proc", 0755)
                        chdir(original_path)
                    Popen(["mount", "-t", "linprocfs", "linproc", self.path +
                           "/root/compat/linux/proc"]).communicate()
            except:
                pass

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

            self.lgr.info("* Starting {} ({})".format(self.uuid, self.conf[
                "tag"]))
            start = Popen(["jail", "-c"] + net +
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
                           "persist"])
            start.communicate()

            if start.returncode:
                self.lgr.info("  + Start FAILED")
            else:
                self.lgr.info("  + Started OK")

            if not ospath.isfile("{}/root/dev/log".format(self.path)):
                original_path = getcwd()
                chdir("{}/root/dev".format(self.path))
                symlink("../var/run/log", "log")
                chdir(original_path)

            self.start_network(vnet)
            # This needs to be a list.
            exec_start = self.conf["exec_start"].split()

            with open("{}/log/{}-console.log".format(self.iocroot,
                                                     self.uuid), "a") as f:
                services = check_call(["jexec",
                                       "ioc-{}".format(self.uuid)] + exec_start,
                                      stdout=f, stderr=PIPE)
            if services:
                self.lgr.info("  + Starting services FAILED")
            else:
                self.lgr.info("  + Starting services OK")

            self.generate_resolv()
            self.set("last_started={}".format(datetime.utcnow().strftime(
                "%F %T")))
            # TODO: DHCP/BPF
            # TODO: Add jailed datasets support
        else:
            self.lgr.error("{} ({}) is already running!".format(self.uuid,
                                                                self.conf[
                                                                    "tag"]))

    def start_network(self, vnet):
        if vnet:
            _, jid = IOCList().get_jid(self.uuid)
            ip4_addr = self.get("ip4_addr")
            defaultgw = self.get("defaultrouter")
            nics = self.get("interfaces").split(",")

            for n in nics:
                nic, bridge = n.split(":")

                try:
                    memberif = Popen(["ifconfig", bridge],
                                     stdout=PIPE).communicate()[0].split()[40]
                    membermtu = Popen(["ifconfig", memberif],
                                      stdout=PIPE).communicate()[0].split()[5]

                    for ip in ip4_addr.split(','):
                        iface, ip4 = ip.split("|")
                        if nic != iface:
                            err = "\n  ERROR: Invalid interface supplied: {}"
                            self.lgr.error(err.format(iface))
                            self.lgr.error("  Did you mean {}?\n".format(nic))
                            equal = False
                        else:
                            equal = True

                        if equal:
                            mac_a, mac_b = self.__generate_vnet_mac__(nic)
                            epair_a_cmd = ["ifconfig", "epair", "create"]
                            epair_a = Popen(epair_a_cmd,
                                            stdout=PIPE).communicate()[0]
                            epair_a = epair_a.strip()
                            epair_b = re.sub("a$", "b", epair_a)

                            try:
                                # Host side
                                check_output(["ifconfig", epair_a, "name",
                                              "{}:{}".format(nic, jid), "mtu",
                                              membermtu], stderr=STDOUT)
                                check_output(["ifconfig", "{}:{}".format(nic,
                                                                         jid),
                                              "link", mac_a], stderr=STDOUT)
                                check_output(["ifconfig", "{}:{}".format(nic,
                                                                         jid),
                                              "description",
                                              "associated with jail:"
                                              " {} ({})".format(self.uuid,
                                                                self.conf[
                                                                    "tag"])],
                                             stderr=STDOUT)

                                # Jail side
                                check_output(["ifconfig", epair_b, "vnet",
                                              "ioc-{}".format(self.uuid)],
                                             stderr=STDOUT)
                                check_output(["jexec", "ioc-{}".format(
                                    self.uuid), "ifconfig", epair_b, "name",
                                              nic, "mtu", membermtu],
                                             stderr=STDOUT)
                                check_output(["jexec", "ioc-{}".format(
                                    self.uuid), "ifconfig", nic, "link", mac_b],
                                             stderr=STDOUT)

                                check_output(["ifconfig", bridge, "addm",
                                              "{}:{}".format(nic, jid), "up"],
                                             stderr=STDOUT)
                                check_output(["ifconfig", "{}:{}".format(nic,
                                                                         jid),
                                              "up"], stderr=STDOUT)
                                check_output(
                                    ["jexec", "ioc-{}".format(self.uuid),
                                     "ifconfig", iface, ip4, "up"],
                                    stderr=STDOUT)
                                check_output(["jexec", "ioc-{}".format(
                                    self.uuid), "route", "add", "default",
                                              defaultgw], stderr=STDOUT)
                            except CalledProcessError as err:
                                raise RuntimeError(
                                    "ERROR: {}".format(err.output.strip()))
                except:
                    pass

    def findscript(self, exec_type):
        # TODO: Do something with this.
        if access("{}/{}".format(self.path, exec_type), X_OK):
            return "{}/{}".format(self.path, exec_type)
        else:
            return self.get("exec_{}".format(exec_type))

    def generate_resolv(self):
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

    def __generate_vnet_mac__(self, nic):
        """
        Generates a random MAC address and checks for uniquness.
        If the jail already has a mac address generated, it will return that
        instead.
        """
        mac = self.get("{}_mac".format(nic))

        if mac == "none":
            jails, paths = IOCList("uuid").get_datasets()
            mac_list = []

            for jail in jails:
                path = paths[jail]
                _conf = IOCJson(path).load_json()
                mac = _conf["mac_prefix"]
                mac_list.append(_conf["{}_mac".format(nic)].split(","))

            # We have to flatten our list of lists.
            mac_list = [m for maclist in mac_list for m in maclist]
            for number in xrange(16 ** 6):
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
