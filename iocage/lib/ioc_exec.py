"""iocage exec module."""
import subprocess as su

import iocage.lib.ioc_common
import iocage.lib.ioc_json
import iocage.lib.ioc_list
import iocage.lib.ioc_start


class IOCExec(object):
    """Run jexec with a user inside the specified jail."""

    def __init__(self, command, uuid, tag, path, host_user="root",
                 jail_user=None, plugin=False, skip=False, console=False,
                 silent=False, callback=None):
        self.command = command
        self.uuid = uuid
        self.tag = tag
        self.path = path
        self.host_user = host_user
        self.jail_user = jail_user
        self.plugin = plugin
        self.skip = skip
        self.console = console
        self.silent = silent
        self.callback = callback

    def exec_jail(self):
        if self.jail_user:
            flag = "-U"
            user = self.jail_user
        else:
            flag = "-u"
            user = self.host_user

        status, _ = iocage.lib.ioc_list.IOCList().list_get_jid(self.uuid)
        conf = iocage.lib.ioc_json.IOCJson(self.path).json_load()
        exec_fib = conf["exec_fib"]
        if not status:
            if not self.plugin and not self.skip:
                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"{self.uuid} ({self.tag}) is not running,"
                               " starting jail"
                },
                    _callback=self.callback,
                    silent=self.silent)

            if conf["type"] in ("jail", "plugin"):
                iocage.lib.ioc_start.IOCStart(self.uuid, self.tag, self.path,
                                              conf,
                                              silent=True)
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

            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": "\nCommand output:"
            },
                _callback=self.callback,
                silent=self.silent)

        if self.plugin:
            try:
                p = su.Popen(["setfib", exec_fib, "jexec", flag, user,
                              f"ioc-{self.uuid}"] + list(self.command),
                             stderr=su.STDOUT, stdin=su.PIPE)
                exec_out = p.communicate(b"\r")[0]
                msg = exec_out if exec_out is not None else ""

                return msg, False
            except su.CalledProcessError as err:
                return err.output.decode("utf-8").rstrip(), True
        elif self.console:
            login_flags = conf["login_flags"].split()
            su.Popen(["setfib", exec_fib, "jexec", f"ioc-{self.uuid}",
                      "login"] + login_flags).communicate()

            return None, False
        else:
            jexec = su.Popen(["setfib", exec_fib, "jexec", flag, user,
                              f"ioc-{self.uuid}"] + list(self.command),
                             stdout=su.PIPE, stderr=su.PIPE)
            msg, err = jexec.communicate()

            return msg, err
