"""This is responsible for starting jails."""
import logging
from datetime import datetime
from shutil import copy
from subprocess import PIPE, Popen

import re
from os import X_OK, access, chdir, getcwd, makedirs, path as ospath, symlink, \
    uname

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


class IOCStart(object):
    """
    Starts jails, the network stack for the jail and generates a resolv file
    for them. It also finds any scripts the user supplies for exec_*
    """

    def __init__(self, uuid, path, silent=False):
        self.pool = IOCJson(" ").get_prop_value("pool")
        self.iocroot = IOCJson(self.pool).get_prop_value("iocroot")

        self.uuid = uuid
        self.path = path
        self.get = IOCJson(self.path, silent=True).get_prop_value
        self.set = IOCJson(self.path, silent=True).set_prop_value
        self.lgr = logging.getLogger('ioc_start')

        if silent:
            self.lgr.disabled = True

    def start_jail(self, jail, conf):
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
            mount_procfs = conf["mount_procfs"]
            host_domainname = conf["host_domainname"]
            host_hostname = conf["host_hostname"]
            securelevel = conf["securelevel"]
            devfs_ruleset = conf["devfs_ruleset"]
            enforce_statfs = conf["enforce_statfs"]
            children_max = conf["children_max"]
            allow_set_hostname = conf["allow_set_hostname"]
            allow_sysvipc = conf["allow_sysvipc"]
            allow_raw_sockets = conf["allow_raw_sockets"]
            allow_chflags = conf["allow_chflags"]
            allow_mount = conf["allow_mount"]
            allow_mount_devfs = conf["allow_mount_devfs"]
            allow_mount_nullfs = conf["allow_mount_nullfs"]
            allow_mount_procfs = conf["allow_mount_procfs"]
            allow_mount_tmpfs = conf["allow_mount_tmpfs"]
            allow_mount_zfs = conf["allow_mount_zfs"]
            allow_quotas = conf["allow_quotas"]
            allow_socket_af = conf["allow_socket_af"]
            exec_prestart = self.findscript("prestart")
            exec_poststart = self.findscript("poststart")
            exec_prestop = self.findscript("prestop")
            exec_stop = conf["exec_stop"]
            exec_clean = conf["exec_clean"]
            exec_timeout = conf["exec_timeout"]
            stop_timeout = conf["stop_timeout"]
            mount_devfs = conf["mount_devfs"]
            mount_fdescfs = conf["mount_fdescfs"]
            sysvmsg = conf["sysvmsg"]
            sysvsem = conf["sysvsem"]
            sysvshm = conf["sysvshm"]

            if mount_procfs == "1":
                Popen(["mount", "-t", "procfs", "proc", self.path +
                       "/root/proc"]).communicate()

            try:
                mount_linprocfs = conf["mount_linprocfs"]

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

            if conf["vnet"] == "off":
                ip4_addr = conf["ip4_addr"]
                ip4_saddrsel = conf["ip4_saddrsel"]
                ip4 = conf["ip4"]
                ip6_addr = conf["ip6_addr"]
                ip6_saddrsel = conf["ip6_saddrsel"]
                ip6 = conf["ip6"]

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

            self.lgr.info("* Starting {} ({})".format(self.uuid, jail))
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
                # TODO: Fancier.
                self.lgr.info("  + Start FAILED")
            else:
                # TODO: Fancier.
                self.lgr.info("  + Started OK")

            if not ospath.isfile("{}/root/dev/log".format(self.path)):
                original_path = getcwd()
                chdir("{}/root/dev".format(self.path))
                symlink("../var/run/log", "log")
                chdir(original_path)

            self.start_network(vnet)
            # TODO: Fancier.
            # This needs to be a list.
            exec_start = conf["exec_start"].split()

            services = Popen(["setfib", conf["exec_fib"], "jexec",
                              "ioc-{}".format(self.uuid)] + exec_start,
                             stdout=PIPE, stderr=PIPE)
            Popen(["tee", "-a", "{}/log/{}-console.log".format(
                self.iocroot, self.uuid)], stdin=PIPE,
                  stdout=PIPE).communicate(
                input=services.communicate()[0])

            if services.returncode:
                self.lgr.info("  + Starting services FAILED")
            else:
                self.lgr.info("  + Starting services OK")

            self.generate_resolv()
            self.set("last_started={}".format(datetime.utcnow().strftime(
                "%F %T")))
            # TODO: DHCP/BPF
            # TODO: Add jailed datasets support
        else:
            raise RuntimeError(jail + " is already running!")

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
                            epair_a_cmd = ["ifconfig", "epair", "create"]
                            epair_a = Popen(epair_a_cmd,
                                            stdout=PIPE).communicate()[0]
                            epair_a = epair_a.strip()
                            epair_b = re.sub("a$", "b", epair_a)

                            Popen(["ifconfig", epair_a, "name", "{}:{}".format(
                                nic, jid), "mtu", membermtu],
                                  stdout=PIPE).communicate()
                            Popen(["ifconfig", epair_b, "vnet", "ioc-{}".format(
                                self.uuid)]).communicate()
                            Popen(["jexec", "ioc-{}".format(self.uuid),
                                   "ifconfig", epair_b, "name", nic, "mtu",
                                   membermtu]).communicate()
                            Popen(["ifconfig", bridge, "addm", "{}:{}".format(
                                nic, jid), "up"]).communicate()
                            Popen(["ifconfig", "{}:{}".format(nic, jid),
                                   "up"]).communicate()
                            Popen(["jexec", "ioc-{}".format(self.uuid),
                                   "ifconfig", iface, ip4, "up"]).communicate()
                            Popen(["jexec", "ioc-{}".format(self.uuid),
                                   "route", "add", "default", defaultgw],
                                  stdout=PIPE).communicate()
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
            with open("{}/root/etc/resolv.conf".format(self.path),
                      "w") as resolv_conf:
                for line in resolver.split(";"):
                    resolv_conf.write(line + "\n")
        elif resolver == "none":
            copy("/etc/resolv.conf", "{}/root/etc/resolv.conf".format(
                self.path))
        else:
            copy(resolver, "{}/root/etc/resolv.conf".format(self.path))
