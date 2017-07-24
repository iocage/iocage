import iocage.lib.JailConfig
import iocage.lib.Network
import iocage.lib.Storage
import iocage.lib.Releases
import iocage.lib.Release
import iocage.lib.helpers

import iocage.lib.ZFSBasejailStorage
import iocage.lib.NullFSBasejailStorage
import iocage.lib.StandaloneJailStorage

import libzfs
import subprocess
import uuid

class Jail:

  def __init__(self, data = {}, zfs=None, host=None, logger=None):

    iocage.lib.helpers.init_logger(self, logger)
    iocage.lib.helpers.init_zfs(self, zfs)
    iocage.lib.helpers.init_host(self, host)

    if isinstance(data, str):
      data = { "uuid": self._resolve_uuid(data) }

    self.config = iocage.lib.JailConfig.JailConfig(data=data, jail=self, logger=self.logger)
    self.networks = []
    self.storage = iocage.lib.Storage.Storage(jail=self, auto_create=True, safe_mode=False, logger=self.logger, zfs=self.zfs)
    self.jail_state = None

    self.config.read()
#    self.update_jail_state()

  @property
  def zfs_pool_name(self):
    return self.host.datasets.root.name.split("/", maxsplit=1)[0]

  def start(self):
    self.require_jail_existing()
    self.require_jail_stopped()
   
    release = self.release
 
    iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage.umount_nullfs(self.storage)

    storage_backend = None
    
    if self.config.basejail_type == "zfs":
      storage_backend = iocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

    if self.config.basejail_type == "nullfs":
      storage_backend = iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage

    # if self.config.type == "clonejail":
    #   pass

    if storage_backend != None:
      storage_backend.apply(self.storage, release)

    self.config.fstab.write()
    self.launch_jail()

    if self.config.vnet:
      self.start_vimage_network()
      self.set_routes()
    
    self.set_nameserver()

    if self.config.jail_zfs == True:
      iocage.lib.ZFSShareStorage.mount_zfs_shares(self.storage)

  def stop(self):
    self.require_jail_existing()
    self.require_jail_running()
    self.destroy_jail()
    self.update_jail_state()

  def create(self, release_name):
    self.require_jail_not_existing()
  
    # check if release exists
    releases = iocage.lib.Releases.Releases(host=self.host, zfs=self.zfs, logger=self.logger)
    try:
      release = releases.find_by_name(release_name)
    except:
      fetched_release = ", ".join(list(map(lambda x: x.name, releases.local)))
      raise Exception(f"Can only create from a fetched release ({fetched_release})")
    self.config.release = release.name

    try:
      if not isinstance(self.uuid, uuid.UUID):
        raise
    except:
      self.config.uuid = uuid.uuid4()

    self.logger.log(f"Creating new Jail with uuid={self.config.uuid}")

    self.storage.create_jail_dataset()
    self.config.fstab.write()

    storage_backend = None

    if self.config.type == "basejail":

      if self.config.basejail_type == "nullfs":
        storage_backend = iocage.lib.NullFSBasejailStorage.NullFSBasejailStorage
      
      elif self.config.basejail_type == "zfs":
        storage_backend = iocage.lib.ZFSBasejailStorage.ZFSBasejailStorage

    elif self.config.type == "clonejail":
      self.config.cloned_release = release.name
      storage_backend = iocage.lib.StandaloneJailStorage.StandaloneJailStorage

    if storage_backend != None:
      storage_backend.setup(self.storage, release)
    
    self.config.data["release"] = release.name
    self.config.save()

  def exec(self, command):
    command = [
      "/usr/sbin/jexec",
      self.identifier
    ] + command
    return iocage.lib.helpers.exec(command)

  def destroy_jail(self):

    command = [ "jail", "-r" ]
    command.append(self.identifier)

    subprocess.check_output(command, shell=False, stderr=subprocess.DEVNULL)

  def launch_jail(self):

    command = [ "jail", "-c" ]

    if self.config.vnet:
      command.append('vnet')
    else:
      ip4_addr = self.config.ip4_addr if self.config.ip4_addr != None else ""
      ip6_addr = self.config.ip6_addr if self.config.ip6_addr != None else ""

      command += [
        f"ip4.addr={ip4_addr}",
        f"ip4.saddrsel={self.config.ip4_saddrsel}",
        f"ip4={self.config.ip4}",
        f"ip6.addr={ip6_addr}",
        f"ip6.saddrsel={self.config.ip6_saddrsel}",
        f"ip6={self.config.ip6}"
      ]

    command += [
      f"name={self.identifier}",
      f"host.hostname={self.config.host_hostname}",
      f"host.domainname={self.config.host_domainname}",
      f"path={self.path}/root",
      #f"securelevel={securelevel}",
      f"host.hostuuid={self.uuid}",
      f"devfs_ruleset={self.config.devfs_ruleset}",
      f"enforce_statfs={self.config.enforce_statfs}",
      f"children.max={self.config.children_max}",
      f"allow.set_hostname={self.config.allow_set_hostname}",
      f"allow.sysvipc={self.config.allow_sysvipc}"
    ]

    if self.host.userland_version > 10.3:
      command += [
        f"sysvmsg={self.config.sysvmsg}",
        f"sysvsem={self.config.sysvsem}",
        f"sysvshm={self.config.sysvshm}"
      ]

    command += [
      f"allow.raw_sockets={self.config.allow_raw_sockets}",
      f"allow.chflags={self.config.allow_chflags}",
      f"allow.mount={self.config.allow_mount}",
      f"allow.mount.devfs={self.config.allow_mount_devfs}",
      f"allow.mount.nullfs={self.config.allow_mount_nullfs}",
      f"allow.mount.procfs={self.config.allow_mount_procfs}",
      f"allow.mount.zfs={self.config.allow_mount_zfs}",
      f"allow.quotas={self.config.allow_quotas}",
      f"allow.socket_af={self.config.allow_socket_af}",
      f"exec.prestart={self.config.exec_prestart}",
      f"exec.poststart={self.config.exec_poststart}",
      f"exec.prestop={self.config.exec_prestop}",
      f"exec.stop={self.config.exec_stop}",
      f"exec.clean={self.config.exec_clean}",
      f"exec.timeout={self.config.exec_timeout}",
      f"stop.timeout={self.config.stop_timeout}",
      f"mount.fstab={self.path}/fstab",
      f"mount.devfs={self.config.mount_devfs}"
    ]

    if self.host.userland_version > 9.3:
      command += [
        f"mount.fdescfs={self.config.mount_fdescfs}",
        f"allow.mount.tmpfs={self.config.allow_mount_tmpfs}"
      ]

    command += [
      "allow.dying",
      f"exec.consolelog={self.logfile_path}",
      "persist"
    ]

    try:
      output = subprocess.check_output(command, shell=False, stderr=subprocess.STDOUT)
      self.update_jail_state()
      self.logger.log(f"Jail '{self.humanreadable_name}' started with JID {self.jid}", jail=self)
    except subprocess.CalledProcessError as exc:
      self.logger.error(f"Jail '{self.humanreadable_name}' failed with exit code {exc.returncode}", jail=self)
      self.logger.verbose(exc.output, jail=self)
      raise

  def start_vimage_network(self):

    self.logger.log("Starting VNET/VIMAGE", jail=self)

    nics = self.config.interfaces
    for nic in nics:

      bridges = list(self.config.interfaces[nic])

      try:
        ipv4_addresses = self.config.ip4_addr[nic]
      except:
        ipv4_addresses = []

      try:
        ipv6_addresses = self.config.ip6_addr[nic]
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

  def set_nameserver(self):
    self.config.resolver.apply(self)

  def set_routes(self):

    self.logger.log(f"Setting Routes (IPv4={self.config.defaultrouter}, IPv6={self.config.defaultrouter6}", jail=self)

    if self.config.defaultrouter:
      self._set_route(self.config.defaultrouter)

    if self.config.defaultrouter6:
      self._set_route(self.config.defaultrouter6, ipv6=True)

  def _set_route(self, gateway, ipv6=False):

    command = [
      "/sbin/route",
      "add"
    ] + (["-6"] if ipv6 else []) + [
      "default",
      gateway
    ]

    self.exec(command)

  def require_jail_not_existing(self):
    if self.exists:
      raise Exception(f"Jail {self.humanreadable_name} already exists")

  def require_jail_existing(self):
    if not self.exists:
      raise Exception(f"Jail {self.humanreadable_name} does not exist")

  def require_jail_stopped(self):
    if self.running:
      raise Exception(f"Jail {self.humanreadable_name} is already running")

  def require_jail_running(self):
    if not self.running:
      raise Exception(f"Jail {self.humanreadable_name} is not running")

  def update_jail_state(self):
    try:
      stdout = subprocess.check_output([
        "/usr/sbin/jls",
        "-j",
        self.identifier,
        "-v",
        "-h"
      ], shell=False, stderr=subprocess.DEVNULL)
      output = stdout.decode("utf-8").strip()

      keys, values = [x.split(" ") for x in output.split("\n")]
      self.jail_state = dict(zip(keys, values))

    except:
      self.jail_state = None

  def _resolve_uuid(self, text):
    jails_dataset = self.host.datasets.jails
    for dataset in list(jails_dataset.children):
      dataset_uuid = dataset.name[len(jails_dataset.name)+1:]
      if text in dataset_uuid:
        self.logger.debug(f"Resolved {text} to uuid {dataset_uuid}")
        return dataset_uuid

    raise Exception(f"No jail matching {text} was found")

  def _get_name(self):
    return self.humanreadable_name

  def _get_humanreadable_name(self):

    try:
      return self.config.name
    except:
      pass

    try:
      return str(self.config.uuid)[:8]
    except:
      pass

    raise Exception("This Jail does not have any identifier yet")

  def _get_stopped(self):
    return self.running != True;

  def _get_running(self):
    return self._get_jid() != None

  def _get_jid(self):
    # self.update_jail_state()
    try:
      return self.jail_state['jid'];
    except:
      return None

  def _get_identifier(self):
    return f"ioc-{self.uuid}"

  def _get_exists(self):
    try:
      self.dataset
      return True
    except:
      return False

  def _get_uuid(self):
    return self.config.uuid

  def _get_release(self):
    return iocage.lib.Release.Release(name=self.config.release)

  def _get_jail_type(self):
    return self.config.type

  def _get_dataset_name(self):
    return f"{self.host.datasets.root.name}/jails/{self.config.uuid}"

  def _get_dataset(self):
    return self.zfs.get_dataset(self._get_dataset_name())

  def _get_path(self):
    return self.dataset.mountpoint

  def _get_logfile_path(self):
    return f"{self.host.datasets.root.mountpoint}/log/{self.identifier}-console.log"

  def __getattr__(self, key):
    try:
      method = self.__getattribute__(f"_get_{key}")
      return method()
    except:
      pass

    if self.jail_state != None:
      try:
        return self.jail_state[key]
      except:
        pass
 
    raise Exception(f"Jail property {key} not found")

  def getattr_str(self, key):
    try:
      return self.__getattr__(key)
    except:
      return "-"

