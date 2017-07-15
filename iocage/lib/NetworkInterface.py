import iocage.lib.helpers

class NetworkInterface:

  ifconfig_command = "/sbin/ifconfig"

  def __init__(self, name="vnet0", ipv4_addresses=[], ipv6_addresses=[], mac=None, mtu=None, description=None, rename=None, addm=None, vnet=None, jail=None, extra_settings=[], auto_apply=True, logger=None):

    self.jail = jail

    self.name = name
    self.ipv4_addresses = ipv4_addresses
    self.ipv6_addresses = ipv6_addresses

    self.extra_settings = extra_settings
    self.settings = {}

    if mac != None:
      self.settings["link"] = mac

    if mtu != None:
      self.settings["mtu"] = str(mtu)

    if description != None:
      self.settings["description"] = f"\"{description}\""

    if vnet != None:
      self.settings["vnet"] = vnet

    if addm != None:
      self.settings["addm"] = addm

    # rename interface when applying settings next time
    if isinstance(rename, str):
      self.rename = True
      self.settings["name"] = rename
    else:
      self.rename = False

    if auto_apply:
      self.apply()


  def apply(self):
    self.apply_settings()
    self.apply_addresses()
    

  def apply_settings(self):
    command = [self.ifconfig_command, self.name]
    for key in self.settings:
      command.append(key)
      command.append(self.settings[key])
    
    if self.extra_settings:
      command += self.extra_settings

    self.exec(command)

    # update name when the interface was renamed
    if self.rename:
      self.name = self.settings["name"]
      del self.settings["name"]
      self.rename = False


  def apply_addresses(self):
    self.__apply_addresses(self.ipv4_addresses, ipv6=False)
    self.__apply_addresses(self.ipv6_addresses, ipv6=True)


  def __apply_addresses(self, addresses, ipv6=False):
    family = "inet6" if ipv6 else "inet"
    for address in addresses:
      command = [self.ifconfig_command, self.name, family, address]
      self.exec(command)


  def exec(self, command, force_local=False):
    if self.__is_jail():
      return self.jail.exec(command)
    else:
      return iocage.lib.helpers.exec(command)


  def __is_jail(self):
    return self.jail != None
