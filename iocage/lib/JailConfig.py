import iocage.lib.JailConfigJSON
import iocage.lib.JailConfigInterfaces
import iocage.lib.JailConfigAddresses
import iocage.lib.JailConfigResolver

from uuid import UUID

class JailConfig(iocage.lib.JailConfigJSON.JailConfigJSON):

  def __init__(self, data = {}):

    object.__setattr__(self, 'data', {})
    object.__setattr__(self, 'dataset', None)
    object.__setattr__(self, 'special_properties', {})

    # the UUID is used in many other variables and needs to be set first
    try:
      self._set_uuid(data.uuid)
    except:
      pass

    # be aware of iocage-legacy jails for migration
    try:
      self.legacy = data.legacy == True
    except:
      self.legacy = False

    self.clone(data);

  def clone(self, data):
    for key in data:
      self.__setattr__(key, data[key])

  def update_special_property(self, name, new_property_handler=None):

    if new_property_handler != None:
      self.special_properties[name] = new_property_handler

    self.data[name] = str(self.special_properties[name])

  def _set_name(self, value):

    self.name = value

    try:
      self.host_hostname
    except:
      self.host_hostname = value
      pass

  def save(self):
    iocage.lib.JailConfigJSON.JailConfigJSON.save(self)

  def _set_uuid(self, uuid):
      object.__setattr__(self, 'uuid', str(UUID(uuid)))

  def _get_ip4_addr(self):
    try:
      return self.special_properties["ip4_addr"]
    except:
      return None
    
  def _set_ip4_addr(self, value):
    self.special_properties["ip4_addr"] = iocage.lib.JailConfigAddresses.JailConfigAddresses(value, jail_config=self, property_name="ip4_addr")
    self.update_special_property("ip4_addr")


  def _get_ip6_addr(self):
    try:
      return self.special_properties["ip6_addr"]
    except:
      return None

  def _set_ip6_addr(self, value):
    self.special_properties["ip6_addr"] = iocage.lib.JailConfigAddresses.JailConfigAddresses(value, jail_config=self, property_name="ip6_addr")
    self.update_special_property("ip6_addr")

  def _get_interfaces(self):
    return self.special_properties["interfaces"]
    
  def _set_interfaces(self, value):
    self.special_properties["interfaces"] = iocage.lib.JailConfigInterfaces.JailConfigInterfaces(value, jail_config=self)
    self.update_special_property("interfaces")

  def _get_defaultrouter(self):
    value = self.data['defaultrouter']
    return value if (value != "none" and value != None) else None

  def _set_defaultrouter(self, value):
    if value == None:
      value = 'none'
    self.data['defaultrouter'] = value

  def _get_defaultrouter6(self):
    value = self.data['defaultrouter6']
    return value if (value != "none" and value != None) else None

  def _set_defaultrouter6(self, value):
    if value == None:
      value = 'none'
    self.data['defaultrouter6'] = value

  def _get_vnet(self):
    return self.data["vnet"] == "on"

  def _set_vnet(self, value):
    vnet_enabled = (value == "on") or (value == True)
    self.data["vnet"] = "on" if vnet_enabled else "off"

  def _get_jail_zfs_dataset(self):
    try:
      return self.data["jail_zfs_dataset"].split()
    except:
      pass
    return []

  def _set_jail_zfs_dataset(self, value):
    value = [value] if isinstance(value, str) else value
    self.data["jail_zfs_dataset"] = " ".join(value)

  def _get_jail_zfs(self):
    enabled = self.data["jail_zfs"] == "on"
    if not enabled:
      if len(self.jail_zfs_dataset) > 0:
        raise Exception("jail_zfs is disabled despite jail_zfs_dataset is configured")
    return enabled

  def _set_jail_zfs(self, value):
    if (value == None) or (value == ""):
      del self.data["jail_zfs"]
      return
    enabled = (value == "on") or (value == True)
    self.data["jail_zfs"] = "on" if enabled else "off"

  def _default_jail_zfs(self):
    # if self.data["jail_zfs"] does not explicitly exist, _get_jail_zfs would raise
    try:
      return len(self.jail_zfs_dataset) > 0
    except:
      return False

  def _default_mac_prefix():
    return "02ff60"

  def _get_resolver(self):
    return self.__create_special_property_resolver()

  def _set_resolver(self, value):
  
    if isinstance(value, str):
      self.data["resolver"] = value
      resolver = self.resolver
    else:
      resolver = iocage.lib.JailConfigResolver.JailConfigResolver(jail_config=self)
      resolver.update(value, notify=True)

  def __create_special_property_resolver(self):
    
    create_new = False
    try:
      self.special_properties["resolver"]
    except:
      create_new = True
      pass

    if create_new:
      resolver = iocage.lib.JailConfigResolver.JailConfigResolver(jail_config=self)
      resolver.update(notify=False)
      self.special_properties["resolver"] = resolver

    return self.special_properties["resolver"]

  def __getattr__(self, key):

    # passthrough existing properties
    try:
      return self.__getattribute__(key)
    except:
      pass

    # data with mappings
    get_method = None
    try:
      get_method = self.__getattribute__(f"_get_{key}")
    except:
      pass

    if get_method:
      return get_method()

    # plain data attribute
    try:
      return self.data[key]
    except:
      pass

    # then fall back to default
    try:
      fallback_method = self.__getattribute__(f"_default_{key}")
      return fallback_method()
    except:
      raise Exception(f"Variable {key} not found")

  def __setattr__(self, key, value):

    # passthrough existing properties
    try:
      self.__getattribute__(key)
      object.__setattr__(self, key, value)
      return
    except:
      pass

    setter_method = None
    try:
      setter_method = self.__getattribute__(f"_set_{key}")
    except:
      self.data[key] = value
      pass

    if setter_method != None:
      return setter_method(value)

  def __str__(self):
    return iocage.lib.JailConfigJSON.JailConfigJSON.toJSON(self)
