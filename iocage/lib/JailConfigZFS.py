# import libzfs

class JailConfigZFS:

  def set_zfs(key, value):
    print(f"set {key}: {value}")

  def get_zfs(key):
    print(f"get {key}")

  def save(self):
    print("SAVE JailConfigZFS")
