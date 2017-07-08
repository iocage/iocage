import json

class JailConfigJSON:

  def __init__(self, data = {}):
    self.options_json = {
      path: f"{self.uuid}"
    }

  def toJSON(self):
    return json.dumps(self.data, sort_keys=True, indent=4)

  def save(self):

    print("Changes would have been written")
    print(JailConfigJSON.toJSON(self))
    return

    # ToDo: read file and see if the contents have changed

    with open(JailConfigJSON.__get_config_json_path(self), "r+") as f:
      f.seek(0)
      f.write(JailConfigJSON.toJSON(self))
      f.truncate()

  def read(self):
    return self.clone(JailConfigJSON.read_data(self))

  def read_data(self):
    with open(JailConfigJSON.__get_config_json_path(self), "r") as conf:
      return json.load(conf)

  def __get_config_json_path(self):
    try:
      return f"{self.dataset.mountpoint}/config.json"
    except:
      raise "Dataset not found or not mounted"
