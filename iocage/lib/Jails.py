from iocage.lib.Jail import Jail

import libzfs

class Jails:

  def __init__(self, root_dataset="zroot/iocage"):
    self.root_dataset = "zroot/iocage"
    self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

  def list(self):
    jails = self._get_existing_jails()
    return jails


  def _get_existing_jails(self):
    jails_dataset = self.zfs.get_dataset(f"{self.root_dataset}/jails")
    jail_datasets = list(jails_dataset.children)

    return list(map(
      lambda x: Jail({
        "uuid": x.name.split("/").pop()
      }),
      jail_datasets
    ))
