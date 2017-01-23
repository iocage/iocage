"""This stops jails."""
import logging
from subprocess import CalledProcessError, PIPE, Popen, check_call

from iocage.lib.ioc_list import IOCList


class IOCStop(object):
    """Stops a jail and unmounts the jails mountpoints."""

    def __init__(self, uuid, jail, path, conf, silent=False):
        self.uuid = uuid
        self.jail = jail
        self.path = path
        self.conf = conf
        self.status, self.jid = IOCList().get_jid(uuid)
        self.nics = conf["interfaces"]
        self.lgr = logging.getLogger('ioc_stop')

        if silent:
            self.lgr.disabled = True

        self.__stop_jail__()

    def __stop_jail__(self):
        # TODO: prestop/poststop with script
        # print("  + Running pre-stop", end="")
        #
        # Format for that ^
        # if:
        #     print("{:>11s}".format("OK"))
        # else:
        #     print("{:>15s}".format("FAILED"))
        #
        # TODO: exec_stop
        if not self.status:
            raise RuntimeError("{} is not running!".format(self.jail))

        self.lgr.info("* Stopping {} ({})".format(self.uuid, self.jail))
        for nic in self.nics.split(","):
            nic = nic.split(":")[0]
            try:
                check_call(["ifconfig", "{}:{}".format(nic, self.jid),
                            "destroy"], stderr=PIPE)
            except CalledProcessError:
                pass

        stop = Popen(["jail", "-r", "ioc-{}".format(self.uuid)],
                     stderr=PIPE)
        stop.communicate()

        # TODO: Fancier.
        if stop.returncode:
            self.lgr.info("  + Removing jail process FAILED")
        else:
            self.lgr.info("  + Removing jail process OK")

        Popen(["umount", "-afF", "{}/fstab".format(self.path)], stderr=PIPE)
        Popen(["umount", "-f", "{}/root/dev/fd".format(self.path)],
              stderr=PIPE).communicate()
        Popen(["umount", "-f", "{}/root/dev".format(self.path)],
              stderr=PIPE).communicate()
        Popen(["umount", "-f", "{}/root/proc".format(self.path)],
              stderr=PIPE).communicate()
        Popen(["umount", "-f", "{}/root/compat/linux/proc".format(self.path)],
              stderr=PIPE).communicate()
