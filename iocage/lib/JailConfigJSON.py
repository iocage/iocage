import json

class JailConfigJSON:

  def __init__(self, data = {}):
    self.options_json = {
      path: f"{self.uuid}"
    }

  def toJSON(self):
    data = list(map(lambda x: x if x != None else "none", self.data))
    return json.dumps(self.data, sort_keys=True, indent=4)

  def save(self):
    config_file_path = JailConfigJSON.__get_config_json_path(self)
    with open(config_file_path, "w") as f:
      f.write(JailConfigJSON.toJSON(self))
      print(f"Config written to {config_file_path}")

  def read(self):
    return self.clone(JailConfigJSON.read_data(self))

  def read_data(self):
    with open(JailConfigJSON.__get_config_json_path(self), "r") as conf:
      return json.load(conf)

  def __get_config_json_path(self):
    try:
      return f"{self.jail.dataset.mountpoint}/config.json"
    except:
      raise "Dataset not found or not mounted"
