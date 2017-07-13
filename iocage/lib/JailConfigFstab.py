import iocage.lib.helpers

class JailConfigFstab:

  def __init__(self, jail):
    self.jail = jail

  @property
  def path(self):
    return f"{self.jail.path}/fstab"

  def write(self):
    with open(self.path, "w") as f:
      f.write(self.__str__())
      print(f"{self.path} written")

  def __str__(self):

    if not self.jail.config.basejail:
      return ""

    fstab_lines = []
    for basedir in iocage.lib.helpers.get_basedir_list():
      release_directory = self.jail.host.datasets.releases

      source = f"{release_directory}/{self.jail.config.cloned_release}/{basedir}"
      destination = f"{self.jail.path}/root/{basedir}"
      fstab_lines.append("\t".join([
        source,
        destination,
        "nullfs",
        "ro",
        "0",
        "0"
      ]))

    return "\n".join(fstab_lines)
