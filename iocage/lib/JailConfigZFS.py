import libzfs


class JailConfigZFS:

    property_prefix = "org.freebsd.iocage:"

    def read(self):

        found = False
        for prop in self.jail.dataset.properties:
            if JailConfigZFS._is_iocage_property(self, prop):
                found = True
                name = JailConfigZFS._get_iocage_property_name(self, prop)
                self.__setattr__(
                    name, self.jail.dataset.properties[prop].value)

        if not found:
            raise Exception("Could not read ZFS config")

        if self.data["basejail"] == "on":
            self.data["basejail"] = "on"
            self.data["basejail_type"] = "zfs"
            self.data["clonejail"] = "off"
        else:
            self.data["basejail"] = "off"
            self.data["clonejail"] = "off"

    def save(self):

        # ToDo: Delete unnecessary ZFS options
        # existing_property_names = list(
        #   map(lambda x: JailConfigZFS._get_iocage_property_name(self, x),
        #     filter(
        #       lambda name: JailConfigZFS._is_iocage_property(self, name),
        #       self.jail.dataset.properties
        #     )
        #   )
        # )
        # data_keys = list(self.data)
        # for existing_property_name in existing_property_names:
        #   if not existing_property_name in data_keys:
        #     pass

        for zfs_property_name in self.data:
            zfs_property = libzfs.ZFSUserProperty(
                str(self.data[zfs_property_name])
            )
            self.jail.dataset.property[zfs_property_name] = zfs_property

    def _is_iocage_property(self, name):
        return name.startswith(JailConfigZFS.property_prefix)

    def _get_iocage_property_name(self, zfs_property_name):
        return zfs_property_name[len(JailConfigZFS.property_prefix):]
