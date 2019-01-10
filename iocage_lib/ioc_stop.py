# Copyright (c) 2014-2019, iocage
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

import iocage_lib.ioc_common
import iocage_lib.ioc_exec
import iocage_lib.ioc_json
import iocage_lib.ioc_list

from pathlib import Path


class IOCStop(object):
    """Stops a jail and unmounts the jails mountpoints."""

    def __init__(
        self, uuid, path, silent=False, callback=None,
        force=False, suppress_exception=False
    ):
        self.pool = iocage_lib.ioc_json.IOCJson(" ").json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.uuid = uuid.replace(".", "_")
        self.path = path
        self.conf = iocage_lib.ioc_json.IOCJson(path).json_get_value('all')
        self.force = force
        self.status, self.jid = iocage_lib.ioc_list.IOCList().list_get_jid(
            uuid)
        self.nics = self.conf["interfaces"]
        self.callback = callback
        self.silent = silent

        try:
            self.__stop_jail__()
        except (Exception, SystemExit) as e:
            if not suppress_exception:
                raise e

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

        failed_message = 'Please use --force flag to force stop jail'
        if not self.force:
            prestop_success, prestop_error = iocage_lib.ioc_common.runscript(
                self.conf['exec_prestop']
            )
            if prestop_error:
                msg = f'  + Executing prestop FAILED\n' \
                    f'ERROR:\n{prestop_error}\n\n{failed_message}'

                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': msg
                },
                    _callback=self.callback,
                    silent=self.silent
                )
            else:
                msg = '  + Executing prestop OK'
                iocage_lib.ioc_common.logit({
                    'level': 'INFO',
                    'message': msg
                },
                    _callback=self.callback,
                    silent=self.silent
                )

            exec_stop = self.conf['exec_stop'].split()
            with open(f'{self.iocroot}/log/{self.uuid}-console.log', 'a') as f:
                output = iocage_lib.ioc_exec.SilentExec(
                    ['setfib', exec_fib, 'jexec', f'ioc-{self.uuid}']
                    + exec_stop, None, unjailed=True, decode=True
                )

                success = output.stdout
                error = output.stderr
                f.write(success or error)

            if error:
                msg = '  + Stopping services FAILED\n' \
                    f'ERROR:\n{error}\n\n{failed_message}'
                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': msg
                },
                    _callback=self.callback,
                    silent=self.silent
                )
            else:
                msg = '  + Stopping services OK'
                iocage_lib.ioc_common.logit({
                    'level': 'INFO',
                    'message': msg
                },
                    _callback=self.callback,
                    silent=self.silent
                )

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

        else:
            # We should remove all exec* keys from jail.conf and make sure
            # we force stop the jail process
            jail_conf = iocage_lib.ioc_json.JailRuntimeConfiguration(self.uuid)
            for r_key in [
                k for k in jail_conf.data if str(k).startswith('exec')
            ]:
                jail_conf.remove(r_key)

            jail_conf.sync_changes()

        # We should still try to destroy the relevant networking
        # related resources if force is true, though we won't raise an
        # exception in that case
        # They haven't set an IP address, this interface won't exist
        destroy_nic = True if dhcp == "on" or ip4_addr != "none" or \
            ip6_addr != "none" else False

        if vnet == "on" and destroy_nic:
            vnet_err = []

            for nic in self.nics.split(","):
                nic = nic.split(":")[0]
                try:
                    iocage_lib.ioc_common.checkoutput(
                        ["ifconfig", f"{nic}.{self.jid}", "destroy"],
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
        if ruleset != '4' and (
            devfs_ruleset == '4' or int(devfs_ruleset) not in ruleset_list
        ):
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
            except su.CalledProcessError:
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

        # Build up a jail stop command.
        cmd = ['jail', '-q']

        # We check for the existence of the jail.conf here as on iocage
        # upgrade people likely will not have these files. These files
        # will be written on the next jail start/restart.
        jail_conf_file = Path(f"/var/run/jail.ioc-{self.uuid}.conf")

        if jail_conf_file.is_file():
            cmd.extend(['-f', str(jail_conf_file)])

        cmd.extend(['-r', f'ioc-{self.uuid}'])

        stop = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE)
        _, stop_err = stop.communicate()

        if stop_err:
            msg = f'  + Removing jail process FAILED:\n' \
                f'{stop_err.decode("utf-8")}'
            iocage_lib.ioc_common.logit({
                'level': 'EXCEPTION',
                'message': msg
            },
                _callback=self.callback,
                silent=self.silent
            )
        else:
            msg = '  + Removing jail process OK'
            iocage_lib.ioc_common.logit({
                'level': 'INFO',
                'message': msg
            },
                _callback=self.callback,
                silent=self.silent
            )

            # If we have issues unlinking, don't let that get in the way. The
            # jail is already stopped so we're happy.
            if jail_conf_file.is_file():
                try:
                    jail_conf_file.unlink()
                except OSError:
                    pass

        poststop_success, poststop_error = iocage_lib.ioc_common.runscript(
            self.conf['exec_poststop']
        )

        if poststop_error:
            # This is the only exec case where we won't raise an exception
            # as jail has already stopped
            msg = f'  + Executing poststop FAILED\n{poststop_error}\n\n' \
                'Jail has been stopped but there may be leftovers ' \
                'from exec_poststop failure'
            iocage_lib.ioc_common.logit({
                'level': 'ERROR',
                'message': msg
            },
                _callback=self.callback,
                silent=self.silent
            )
        else:
            msg = '  + Executing poststop OK'
            iocage_lib.ioc_common.logit({
                'level': 'INFO',
                'message': msg
            },
                _callback=self.callback,
                silent=self.silent
            )

        for command in [
            ['umount', '-afF', f'{self.path}/fstab'],
            ['umount', '-f', f'{self.path}/root/dev/fd'],
            ['umount', '-f', f'{self.path}/root/dev'],
            ['umount', '-f', f'{self.path}/root/proc'],
            ['umount', '-f', f'{self.path}/root/compat/linux/proc']
        ]:
            su.Popen(
                command,
                stderr=su.PIPE
            ).communicate()
