"""iocage exec module."""
from subprocess import CalledProcessError, PIPE, Popen, STDOUT

from iocage.lib.ioc_common import checkoutput, logit
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart


class IOCExec(object):
    """Run jexec with a user inside the specified jail."""

    def __init__(self, command, uuid, tag, path, host_user="root",
                 jail_user=None, plugin=False, skip=False, silent=False,
                 callback=None):
        self.command = command
        self.uuid = uuid
        self.tag = tag
        self.path = path
        self.host_user = host_user
        self.jail_user = jail_user
        self.plugin = plugin
        self.skip = skip
        self.silent = silent
        self.callback = callback

    def exec_jail(self):
        if self.jail_user:
            flag = "-U"
            user = self.jail_user
        else:
            flag = "-u"
            user = self.host_user

        status, _ = IOCList().list_get_jid(self.uuid)
        conf = IOCJson(self.path).json_load()
        exec_fib = conf["exec_fib"]
        if not status:
            if not self.plugin and not self.skip:
                logit({
                    "level"  : "INFO",
                    "message": f"{self.uuid} ({self.tag}) is not running,"
                               " starting jail"
                },
                    _callback=self.callback,
                    silent=self.silent)

            if conf["type"] in ("jail", "plugin"):
                IOCStart(self.uuid, self.tag, self.path, conf, silent=True)
            elif conf["type"] == "basejail":
                raise RuntimeError(
                    "Please run \"iocage migrate\" before trying to start"
                    f" {self.uuid} ({self.tag})")
            elif conf["type"] == "template":
                raise RuntimeError(
                    "Please convert back to a jail before trying to start"
                    f" {self.uuid} ({self.tag})")
            else:
                raise RuntimeError(f"{conf['type']} is not a supported jail"
                                   " type.")

            logit({
                "level"  : "INFO",
                "message": "\nCommand output:"
            },
                _callback=self.callback,
                silent=self.silent)

        if self.plugin:
            try:
                checkoutput(["setfib", exec_fib, "jexec", flag, user,
                             f"ioc-{self.uuid}"] + list(self.command),
                            stderr=STDOUT)
            except CalledProcessError as err:
                return err.output.decode("utf-8").rstrip()
        else:
            jexec = Popen(["setfib", exec_fib, "jexec", flag, user,
                           f"ioc-{self.uuid}"] + list(self.command),
                          stdout=PIPE, stderr=PIPE)
            msg, err = jexec.communicate()

            return msg, err
