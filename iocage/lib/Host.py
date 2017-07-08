import os

class Host:

  @property
  def userland_version(self):
    return float(os.uname()[2].partition("-")[0])
