"""This stops jails."""
import os
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_call

from iocage.lib.ioc_common import checkoutput, logit
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


class IOCStop(object):
    """Stops a jail and unmounts the jails mountpoints."""

    def __init__(self, uuid, jail, path, conf, silent=False, callback=None):
        self.pool = IOCJson(" ").json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.uuid = uuid
        self.jail = jail
        self.path = path
        self.conf = conf
        self.status, self.jid = IOCList().list_get_jid(uuid)
        self.nics = conf["interfaces"]
        self.callback = callback
        self.silent = silent

        self.__stop_jail__()

    def runscript(self, script):
        if os.access(script, os.X_OK):
            # 0 if success
            try:
                out = checkoutput(script, stderr=STDOUT)
            except CalledProcessError as err:
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
            logit({
                      "level"  : "ERROR",
                      "message": msg
                  },
                  _callback=self.callback,
                  silent=self.silent)
        else:
            msg = f"* Stopping {self.uuid} ({self.conf['tag']})"
            logit({
                "level"  : "INFO",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

            prestop, prestop_err = self.runscript(self.conf["exec_prestop"])

            if prestop and prestop_err:
                msg = f"  + Running prestop WARNING\n{prestop_err}"
                logit({
                    "level"  : "WARNING",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            elif prestop:
                msg = "  + Running prestop OK"
                logit({
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

                logit({
                    "level"  : "ERROR",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

            exec_stop = self.conf["exec_stop"].split()
            with open("{}/log/{}-console.log".format(self.iocroot,
                                                     self.uuid), "a") as f:
                services = check_call(["setfib", exec_fib, "jexec",
                                       f"ioc-{self.uuid}"] + exec_stop,
                                      stdout=f, stderr=PIPE)
            if services:
                msg = "  + Stopping services FAILED"
                logit({
                          "level"  : "ERROR",
                          "message": msg
                      },
                      _callback=self.callback,
                      silent=self.silent)
            else:
                msg = "  + Stopping services OK"
                logit({
                          "level"  : "INFO",
                          "message": msg
                      },
                      _callback=self.callback,
                      silent=self.silent)

            if self.conf["jail_zfs"] == "on":
                for jdataset in self.conf["jail_zfs_dataset"].split():
                    jdataset = jdataset.strip()
                    children = checkoutput(["zfs", "list", "-H", "-r", "-o",
                                            "name", "-S", "name",
                                            "{}/{}".format(self.pool,
                                                           jdataset)])

                    for child in children.split():
                        child = child.strip()

                        try:
                            checkoutput(["setfib", exec_fib, "jexec",
                                         f"ioc-{self.uuid}", "zfs", "umount",
                                         child], stderr=STDOUT)
                        except CalledProcessError as err:
                            mountpoint = checkoutput(["zfs", "get", "-H",
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
                        checkoutput(["zfs", "unjail", "ioc-{}".format(
                            self.uuid), "{}/{}".format(self.pool, jdataset)],
                                    stderr=STDOUT)
                    except CalledProcessError as err:
                        raise RuntimeError(
                            "{}".format(
                                err.output.decode("utf-8").rstrip()))

            if vnet == "on":
                for nic in self.nics.split(","):
                    nic = nic.split(":")[0]
                    try:
                        checkoutput(
                            ["ifconfig", "{}:{}".format(nic, self.jid),
                             "destroy"], stderr=STDOUT)
                    except CalledProcessError:
                        pass

            if ip4_addr != "inherit" and vnet == "off":
                if ip4_addr != "none":
                    for ip4 in ip4_addr.split(","):
                        try:
                            iface, addr = ip4.split("/")[0].split("|")
                            addr = addr.split()
                            checkoutput(["ifconfig", iface] + addr +
                                         ["-alias"], stderr=STDOUT)
                        except ValueError:
                            # Likely a misconfigured ip_addr with no interface.
                            msg = "  ! IP4 address is missing an interface," \
                                  " set ip4_addr to \"INTERFACE|IPADDR\""
                            logit({
                                      "level"  : "INFO",
                                      "message": msg
                                  },
                                  _callback=self.callback,
                                  silent=self.silent)
                        except CalledProcessError as err:
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
                            checkoutput(["ifconfig", iface, "inet6"] + addr +
                                         ["-alias"], stderr=STDOUT)
                        except ValueError:
                            # Likely a misconfigured ip_addr with no interface.
                            msg = "  ! IP6 address is missing an interface," \
                                  " set ip6_addr to \"INTERFACE|IPADDR\""
                            logit({
                                      "level"  : "INFO",
                                      "message": msg
                                  },
                                  _callback=self.callback,
                                  silent=self.silent)
                        except CalledProcessError as err:
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

            stop = check_call(["jail", "-r", "ioc-{}".format(self.uuid)],
                              stderr=PIPE)

            if stop:
                msg = "  + Removing jail process FAILED"
                logit({
                          "level"  : "ERROR",
                          "message": msg
                      },
                      _callback=self.callback,
                      silent=self.silent)
            else:
                msg = "  + Removing jail process OK"
                logit({
                          "level"  : "INFO",
                          "message": msg
                      },
                      _callback=self.callback,
                      silent=self.silent)

            poststop, poststop_err = self.runscript(self.conf["exec_poststop"])

            if poststop and poststop_err:
                msg = f"  + Running poststop WARNING\n{poststop_err}"
                logit({
                    "level"  : "WARNING",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)
            elif poststop:
                msg = "  + Running poststop OK"
                logit({
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

                logit({
                    "level"  : "ERROR",
                    "message": msg
                },
                    _callback=self.callback,
                    silent=self.silent)

            Popen(["umount", "-afF", "{}/fstab".format(self.path)],
                  stderr=PIPE).communicate()
            Popen(["umount", "-f", "{}/root/dev/fd".format(self.path)],
                  stderr=PIPE).communicate()
            Popen(["umount", "-f", "{}/root/dev".format(self.path)],
                  stderr=PIPE).communicate()
            Popen(["umount", "-f", "{}/root/proc".format(self.path)],
                  stderr=PIPE).communicate()
            Popen(
                ["umount", "-f",
                 "{}/root/compat/linux/proc".format(self.path)],
                stderr=PIPE).communicate()
