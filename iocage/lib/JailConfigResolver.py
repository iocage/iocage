import iocage.lib.helpers

import shutil

class JailConfigResolver(list):

  def __init__(self, jail_config, logger=None):
    list.__init__(self, [])
    iocage.lib.helpers.init_logger(self, logger)
    self.jail_config = jail_config
    self.jail_config.update_special_property("resolver", new_property_handler=self)

  @property
  def conf_file_path(self):
    return "/etc/resolv.conf"

  @property
  def method(self):
    if self.value == "/etc/resolv.conf":
      return "copy"

    elif self.value == "/dev/null":
      return "skip"

    else:
      return "manual"

  @property
  def value(self):
    return self.jail_config.data["resolver"]

  def apply(self, jail):

    self.logger.log(f"Configuring nameserver for Jail '{jail.humanreadable_name}'")
      
    remote_path = f"{jail.path}/root{self.conf_file_path}"

    if self.method == "copy":
      shutil.copy(self.conf_file_path, remote_path)
      self.logger.verbose("resolv.conf copied from host")

    elif self.method == "manual":
      with open(remote_path, "w") as f:
        f.write("\n".join(self))
        f.close()
      self.logger.verbose("resolv.conf written manually")

    else:
     self.logger.verbose("resolv.conf not touched")

  def update(self, value=None, notify=True):
    value = value if value != None else self.value
    self.clear()

    if self.method == "manual":
      if isinstance(value, str):
        self += value.split(";")
      else:
        self += value
    else:
      self.append(value, notify=False)

    self.__notify(notify)


  def append(self, value, notify=True):
    list.append(self, value)
    self.__notify(notify)


  def __setitem__(self, key, value, notify=True):
    list.__setitem__(self, key, value)
    self.__notify(notify)

  def __str__(self):
    out = ";".join(list(self))
    return out

  def __notify(self, notify=True):

    if not notify:
      return

    try:
      self.jail_config.update_special_property("resolver")
    except:
      raise

