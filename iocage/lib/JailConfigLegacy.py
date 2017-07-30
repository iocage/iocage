import os
import ucl


class JailConfigLegacy:

    def read(self):
        self.clone(JailConfigLegacy.read_data(self))

    def save(self):
        config_file_path = JailConfigLegacy.__get_config_path(self)
        with open(config_file_path, "w") as f:
            f.write(JailConfigLegacy.toLegacyConfig(self))
            print(f"Legacy config written to {config_file_path}")

    def read_data(self):
        with open(JailConfigLegacy.__get_config_path(self), "r") as conf:
            data = ucl.load(conf.read())

            try:
                if data["type"] == "basejail":
                    data["basejail"] = "on"
                    data["clonejail"] = "off"
                    data["basejail_type"] = "zfs"
                    data["type"] = "jail"
            except:
                pass

            return data

    def __get_config_path(self):
        try:
            return f"{self.jail.dataset.mountpoint}/config"
        except:
            raise "Dataset not found or not mounted"
