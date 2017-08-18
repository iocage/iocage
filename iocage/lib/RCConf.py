import os
import ucl

import iocage.lib.helpers

class RCConf(dict):

    def __init__(self, path, data={}, logger=None, jail=None):

        dict.__init__(self, {})
        iocage.lib.helpers.init_logger(self, logger=logger)
        self.jail = jail

        # No file was loaded yet, so we can't know the delta yet
        self._file_content_changed = True
        self._path = None
        self.path = path

    @property
    def path(self):
        return object.__getattribute__(self, "_path")

    @path.setter
    def path(self, value):
        if self.path != value:
            new_path = None if value is None else os.path.realpath(value) 
            dict.__setattr__(self, "_path", new_path)
            self._read_file()

    def _read_file(self, silent=False, delete=False):
        try:
            if (self.path is not None) and os.path.isfile(self.path):
                data = self._read(silent=silent)
        except:
            data = {}
            pass

        existing_keys = set(self.keys())
        new_keys = set(data.keys())
        delete_keys = existing_keys - new_keys

        if delete is True:
            for key in delete_keys:
                del self[key]

        for key in new_keys:
            self[key] = data[key]

        if silent is False:
            self.logger.verbose(f"Updated rc.conf data from {self.path}")

        if delete is False and len(delete_keys) > 0:
            # There are properties that are not in the file
            self._file_content_changed = True
        else:
            # Current data matches with file contents
            self._file_content_changed = False

    def _read(self, silent=False):
        data = ucl.load(open(self.path).read())
        self.logger.spam(
            f"rc.conf was read from {self.path}",
            jail=self.jail
        )
        return data

    def save(self):

        if self._file_content_changed is False:
            self.logger.debug("rc.conf was not modified - skipping write")
            return

        with open(self.path, "w") as rcconf:

            output = ucl.dump(self, ucl.UCL_EMIT_CONFIG)
            output = output.replace(" = \"", "=\"")
            output = output.replace("\";\n", "\"\n")

            self.logger.verbose(
                f"Writing rc.conf to {self.path}",
                jail=self.jail
            )

            rcconf.write(output)
            rcconf.truncate()
            rcconf.close()

            self.logger.spam(output[:-1], jail=self.jail, indent=1)

    def __setitem__(self, key, value):

        if isinstance(value, str):
            if value.lower() == "yes":
                value = True
            elif value.lower() == "no":
                value = False

        if value is True:
            dict.__setitem__(self, key, "YES")
        elif value is False:
            dict.__setitem__(self, key, "No")
        else:
            dict.__setitem__(self, key, str(value))

    def __getitem__(self, key):
        value = dict.__getitem__(self, key)
        if value.lower() == "YES":
            return True
        elif value.lower() == "NO":
            return False
        else:
            return value
