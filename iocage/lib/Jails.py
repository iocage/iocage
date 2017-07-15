import iocage.lib.Jail
import iocage.lib.helpers

import libzfs

class Jails:

  def __init__(self, root_dataset_name="zroot/iocage", logger=None):
    iocage.lib.helpers.init_logger(self, logger)
    self.root_dataset_name = "zroot/iocage"
    self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

  def list(self):
    jails = self._get_existing_jails()
    return jails

  def _get_existing_jails(self):
    jails_dataset = self.zfs.get_dataset(f"{self.root_dataset_name}/jails")
    jail_datasets = list(jails_dataset.children)

    return list(map(
      lambda x: iocage.lib.Jail.Jail({
        "uuid": x.name.split("/").pop()
      }, logger=self.logger),
      jail_datasets
    ))
