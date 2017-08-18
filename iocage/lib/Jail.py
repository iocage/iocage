import iocage.lib.JailConfig
import iocage.lib.Network
import iocage.lib.Storage
import iocage.lib.Releases
import iocage.lib.Release
import iocage.lib.RCConf
import iocage.lib.helpers
import iocage.lib.errors

import iocage.lib.ZFSBasejailStorage
import iocage.lib.ZFSShareStorage
import iocage.lib.NullFSBasejailStorage
import iocage.lib.StandaloneJailStorage

import subprocess
import uuid
import os


class Jail:

    def __init__(self, data={}, zfs=None, host=None, logger=None, new=False):

        iocage.lib.helpers.init_logger(self, logger)
        iocage.lib.helpers.init_zfs(self, zfs)
        iocage.lib.helpers.init_host(self, host)

        if isinstance(data, str):
            data = {"id": self._resolve_name(data)}

        self.config = iocage.lib.JailConfig.JailConfig(
            data=data,
            jail=self,
            logger=self.logger
        )

        self.networks = []

        self.storage = iocage.lib.Storage.Storage(
            auto_create=True, safe_mode=False,
            jail=self, logger=self.logger, zfs=self.zfs)

        self.jail_state = None
        self._dataset_name = None
        self._rc_conf = None

        if new is False:
            self.config.read()

    @property
    def zfs_pool_name(self):
        return self.host.datasets.root.name.split("/", maxsplit=1)[0]

    @property
    def _rc_conf_path(self):
        return f"{self.path}/root/etc/rc.conf"

    @property
    def rc_conf(self):
        if self._rc_conf is None:
            self._rc_conf = iocage.lib.RCConf.RCConf(
                path=self._rc_conf_path,
                jail=self,
                logger=self.logger
            )
        return self._rc_conf

    def start(self):
        self.require_jail_existing()
        self.require_jail_stopped()

        release = self.release

        backend = None

        if self.config["basejail_type"] == "zfs":
            backend = iocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

        if self.config["basejail_type"] == "nullfs":
            backend = iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage

        if backend is not None:
            backend.apply(self.storage, release)

        self.config.fstab.read_file()
        self.config.fstab.save_with_basedirs()
        self.launch_jail()

        if self.config["vnet"]:
            self.start_vimage_network()
            self.set_routes()

        self.set_nameserver()

        if self.config["jail_zfs"] is True:
            iocage.lib.ZFSShareStorage.ZFSShareStorage.mount_zfs_shares(
                self.storage
            )

    def stop(self, force=False):

        if force is True:
            return self.force_stop()

        self.require_jail_existing()
        self.require_jail_running()
        self.destroy_jail()
        if self.config["vnet"]:
            self.stop_vimage_network()
        self._teardown_mounts()
        self.update_jail_state()

    def destroy(self, force=False):

        self.update_jail_state()

        if self.running is True and force is True:
            self.stop(force=True)
        else:
            self.require_jail_stopped()

        self.storage.delete_dataset_recursive(self.dataset)

    def force_stop(self):

        successful = True

        try:
            self.destroy_jail()
        except Exception as e:
            successful = False
            self.logger.warn(str(e))

        if self.config["vnet"]:
            try:
                self.stop_vimage_network()
            except Exception as e:
                successful = False
                self.logger.warn(str(e))

        try:
            self._teardown_mounts()
        except Exception as e:
            successful = False
            self.logger.warn(str(e))

        try:
            self.update_jail_state()
        except Exception as e:
            successful = False
            self.logger.warn(str(e))

        return successful

    def create(self, release_name, auto_download=False):
        self.require_jail_not_existing()

        # check if release exists
        releases = iocage.lib.Releases.Releases(
            host=self.host,
            zfs=self.zfs,
            logger=self.logger
        )

        filteres_released = list(filter(
            lambda x: x.name == release_name,
            releases.local
        ))

        if len(filteres_released) == 0:
            raise iocage.lib.errors.ReleaseNotFetched(
                release_name,
                logger=self.logger
            )

        release = filteres_released[0]
        self.config["release"] = release.name

        if not self.config["id"]:
            self.config["name"] = str(uuid.uuid4())

        self.logger.verbose(
            f"Creating jail '{self.config['id']}'",
            jail=self
        )

        for key, value in self.config.data.items():
            msg = f"{key} = {value}"
            self.logger.spam(msg, jail=self, indent=1)

        self.storage.create_jail_dataset()
        self.config.fstab.update()

        backend = None

        is_basejail = self.config["type"] == "basejail"
        if not is_basejail:
            backend = iocage.lib.StandaloneJailStorage.StandaloneJailStorage
        if is_basejail and self.config["basejail_type"] == "nullfs":
            backend = iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage
        elif is_basejail and self.config["basejail_type"] == "zfs":
            backend = iocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

        if backend is not None:
            backend.setup(self.storage, release)

        self.config.data["release"] = release.name
        self.config.save()

    def exec(self, command, **kwargs):
        command = [
            "/usr/sbin/jexec",
            self.identifier
        ] + command
        return iocage.lib.helpers.exec(command, logger=self.logger, **kwargs)

    def passthru(self, command):

        if isinstance(command, str):
            command = [command]

        return iocage.lib.helpers.exec_passthru(
            [
                "/usr/sbin/jexec",
                self.identifier
            ] + command,
            logger=self.logger
        )

    def exec_console(self):
        return self.passthru(
            ["/usr/bin/login"] + self.config["login_flags"]
        )

    def destroy_jail(self):

        command = ["jail", "-r"]
        command.append(self.identifier)

        subprocess.check_output(
            command,
            shell=False,
            stderr=subprocess.DEVNULL
        )

    def launch_jail(self):

        command = ["jail", "-c"]

        if self.config["vnet"]:
            command.append('vnet')
        else:

            if self.config["ip4_addr"] is not None:
                ip4_addr = self.config["ip4_addr"]
                command += [
                    f"ip4.addr={ip4_addr}",
                    f"ip4.saddrsel={self.config['ip4_saddrsel']}",
                    f"ip4={self.config['ip4']}",
                ]

            if self.config['ip6_addr'] is not None:
                ip6_addr = self.config['ip6_addr']
                command += [
                    f"ip6.addr={ip6_addr}",
                    f"ip6.saddrsel={self.config['ip6_saddrsel']}",
                    f"ip6={self.config['ip6']}",
                ]

        command += [
            f"name={self.identifier}",
            f"host.hostname={self.config['host_hostname']}",
            f"host.domainname={self.config['host_domainname']}",
            f"path={self.path}/root",
            f"securelevel={self.config['securelevel']}",
            f"host.hostuuid={self.name}",
            f"devfs_ruleset={self.config['devfs_ruleset']}",
            f"enforce_statfs={self.config['enforce_statfs']}",
            f"children.max={self.config['children_max']}",
            f"allow.set_hostname={self.config['allow_set_hostname']}",
            f"allow.sysvipc={self.config['allow_sysvipc']}"
        ]

        if self.host.userland_version > 10.3:
            command += [
                f"sysvmsg={self.config['sysvmsg']}",
                f"sysvsem={self.config['sysvsem']}",
                f"sysvshm={self.config['sysvshm']}"
            ]

        command += [
            f"allow.raw_sockets={self.config['allow_raw_sockets']}",
            f"allow.chflags={self.config['allow_chflags']}",
            f"allow.mount={self.config['allow_mount']}",
            f"allow.mount.devfs={self.config['allow_mount_devfs']}",
            f"allow.mount.nullfs={self.config['allow_mount_nullfs']}",
            f"allow.mount.procfs={self.config['allow_mount_procfs']}",
            f"allow.mount.zfs={self.config['allow_mount_zfs']}",
            f"allow.quotas={self.config['allow_quotas']}",
            f"allow.socket_af={self.config['allow_socket_af']}",
            f"exec.prestart={self.config['exec_prestart']}",
            f"exec.poststart={self.config['exec_poststart']}",
            f"exec.prestop={self.config['exec_prestop']}",
            f"exec.start={self.config['exec_start']}",
            f"exec.stop={self.config['exec_stop']}",
            f"exec.clean={self.config['exec_clean']}",
            f"exec.timeout={self.config['exec_timeout']}",
            f"stop.timeout={self.config['stop_timeout']}",
            f"mount.fstab={self.path}/fstab",
            f"mount.devfs={self.config['mount_devfs']}"
        ]

        if self.host.userland_version > 9.3:
            command += [
                f"mount.fdescfs={self.config['mount_fdescfs']}",
                f"allow.mount.tmpfs={self.config['allow_mount_tmpfs']}"
            ]

        command += [
            "allow.dying",
            f"exec.consolelog={self.logfile_path}",
            "persist"
        ]

        humanreadable_name = self.humanreadable_name
        try:
            iocage.lib.helpers.exec(command, logger=self.logger)
            self.update_jail_state()
            self.logger.verbose(
                f"Jail '{humanreadable_name}' started with JID {self.jid}",
                jail=self
            )
        except subprocess.CalledProcessError as exc:
            code = exc.returncode
            self.logger.error(
                f"Jail '{humanreadable_name}' failed with exit code {code}",
                jail=self
            )
            raise

    def start_vimage_network(self):

        self.logger.log("Starting VNET/VIMAGE", jail=self)

        nics = self.config["interfaces"]
        for nic in nics:

            bridges = list(self.config["interfaces"][nic])

            try:
                ipv4_addresses = self.config["ip4_addr"][nic]
            except:
                ipv4_addresses = []

            try:
                ipv6_addresses = self.config["ip6_addr"][nic]
            except:
                ipv6_addresses = []

            net = iocage.lib.Network.Network(
                jail=self,
                nic=nic,
                ipv4_addresses=ipv4_addresses,
                ipv6_addresses=ipv6_addresses,
                bridges=bridges,
                logger=self.logger
            )
            net.setup()
            self.networks.append(net)

    def stop_vimage_network(self):
        for network in self.networks:
            network.teardown()
            self.networks.remove(network)

    def set_nameserver(self):
        self.config["resolver"].apply(self)

    def set_routes(self):

        defaultrouter = self.config["defaultrouter"]
        defaultrouter6 = self.config["defaultrouter6"]

        if not defaultrouter or defaultrouter6:
            self.logger.spam("no static routes configured")
            return

        if defaultrouter:
            self.logger.verbose(
                f"setting default IPv4 gateway to {defaultrouter}",
                jail=self
            )
            self._set_route(defaultrouter)

        if defaultrouter6:
            self._set_route(defaultrouter6, ipv6=True)

    def _set_route(self, gateway, ipv6=False):

        ip_version = 4 + 2 * (ipv6 is True)

        self.logger.verbose(
            f"setting default IPv{ip_version} gateway to {gateway}",
            jail=self
        )

        command = [
            "/sbin/route",
            "add"
        ] + (["-6"] if (ipv6 is True) else []) + [
            "default",
            gateway
        ]

        self.exec(command)

    def require_jail_not_existing(self):
        if self.exists:
            raise iocage.lib.errors.JailAlreadyExists(
                jail=self,
                logger=self.logger
            )

    def require_jail_existing(self):
        if not self.exists:
            raise iocage.lib.errors.JailDoesNotExist(
                jail=self,
                logger=self.logger
            )

    def require_jail_stopped(self):
        if self.running:
            raise iocage.lib.errors.JailAlreadyRunning(
                jail=self,
                logger=self.logger
            )

    def require_jail_running(self):
        if not self.running:
            raise iocage.lib.errors.JailNotRunning(
                jail=self,
                logger=self.logger
            )

    def update_jail_state(self):
        try:
            stdout = subprocess.check_output([
                "/usr/sbin/jls",
                "-j",
                self.identifier,
                "-v",
                "-h"
            ], shell=False, stderr=subprocess.DEVNULL)
            output = stdout.decode().strip()

            keys, values = [x.split(" ") for x in output.split("\n")]
            self.jail_state = dict(zip(keys, values))

        except:
            self.jail_state = None

    def _teardown_mounts(self):

        mountpoints = list(map(
            lambda mountpoint: f"{self.path}/root{mountpoint}",
            [
                "/dev/fd",
                "/dev",
                "/proc",
                "/root/compat/linux/proc"
            ]
        ))

        mountpoints += list(map(lambda x: x["destination"],
                                list(self.config.fstab)))

        for mountpoint in mountpoints:
            if os.path.isdir(mountpoint):
                iocage.lib.helpers.umount(
                    mountpoint,
                    force=True,
                    ignore_error=True  # maybe it was not mounted
                )

    def _resolve_name(self, text):
        jails_dataset = self.host.datasets.jails
        best_guess = ""
        for dataset in list(jails_dataset.children):
            dataset_name = dataset.name[(len(jails_dataset.name) + 1):]
            if text == dataset_name:
                # Exact match, immediately return
                return dataset_name
            elif dataset_name.startswith(text) and len(text) > len(best_guess):
                best_guess = text

        if len(best_guess) > 0:
            self.logger.debug(f"Resolved {text} to uuid {dataset_name}")
            return best_guess

        raise iocage.lib.errors.JailNotFound(text, logger=self.logger)

    def _get_name(self):
        return self.config["id"]

    def _get_humanreadable_name(self):

        try:
            uuid.UUID(self.name)
            return str(self.name)[:8]
        except (TypeError, ValueError):
            pass

        try:
            return self.name
        except AttributeError:
            pass

        raise iocage.lib.errors.JailUnknownIdentifier(logger=self.logger)

    def _get_stopped(self):
        return self.running is not True

    def _get_running(self):
        return self._get_jid() is not None

    def _get_jid(self):
        try:
            return self.jail_state["jid"]
        except (TypeError, AttributeError, KeyError):
            pass

        try:
            self.update_jail_state()
            return self.jail_state["jid"]
        except (TypeError, AttributeError, KeyError):
            return None

    def _get_identifier(self):
        return f"ioc-{self.config['id']}"

    def _get_exists(self):
        try:
            self.dataset
            return True
        except:
            return False

    def _get_release(self):
        return iocage.lib.Release.Release(
            name=self.config["release"],
            logger=self.logger,
            host=self.host,
            zfs=self.zfs
        )

    def _get_jail_type(self):
        return self.config["type"]

    def set_dataset_name(self, value=None):
        self._dataset_name = value

    def _get_dataset_name(self):
        if self._dataset_name is not None:
            return self._dataset_name
        else:
            return f"{self.host.datasets.root.name}/jails/{self.config['id']}"

    def _get_dataset(self):
        return self.zfs.get_dataset(self._get_dataset_name())

    def _get_path(self):
        return self.dataset.mountpoint

    def _get_logfile_path(self):
        return f"{self.host.datasets.logs.mountpoint}-console.log"

    def __getattr__(self, key):

        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            pass

        try:
            method = object.__getattribute__(self, f"_get_{key}")
            return method()
        except:
            pass

        try:
            jail_state = object.__getattribute__(self, "jail_state")
        except:
            jail_state = None
            raise

        if jail_state is not None:
            try:
                return jail_state[key]
            except:
                pass

        raise AttributeError(f"Jail property {key} not found")

    def getattr_str(self, key):
        try:
            return str(self.__getattr__(key))
        except AttributeError:
            return "-"

    def __dir__(self):

        properties = set()

        for prop in dict.__dir__(self):
            if prop.startswith("_get_"):
                properties.add(prop[5:])
            elif not prop.startswith("_"):
                properties.add(prop)

        return list(properties)
