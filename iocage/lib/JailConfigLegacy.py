import ucl
import os.path


class JailConfigLegacy:

    def read(self):
        self.clone(JailConfigLegacy.read_data(self), skip_on_error=True)

    def save(self):
        config_file_path = JailConfigLegacy.__get_config_path(self)
        with open(config_file_path, "w") as f:
            f.write(JailConfigLegacy.toLegacyConfig(self))
            self.logger.verbose(f"Legacy config written to {config_file_path}")

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

    def exists(self):
        return os.path.isfile(JailConfigLegacy.__get_config_path(self))

    def __get_config_path(self):
        try:
            return f"{self.jail.dataset.mountpoint}/config"
        except:
            raise "Dataset not found or not mounted"
