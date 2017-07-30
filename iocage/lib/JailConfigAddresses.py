class AddressSet(set):

    def __init__(self, jail_config=None, property_name="ip4_address"):
        self.jail_config = jail_config
        set.__init__(self)
        object.__setattr__(self, 'property_name', property_name)

    def add(self, value, notify=True):
        set.add(self, value)
        if notify:
            self.__notify()

    def remove(self, value, notify=True):
        set.remove(self, value)
        if notify:
            self.__notify()

    def __notify(self):
        try:
            self.jail_config.update_special_property(self.property_name)
        except:
            raise


class JailConfigAddresses(dict):

    def __init__(self, value, jail_config=None, property_name="ip4_address"):
        dict.__init__(self, {})
        dict.__setattr__(self, 'jail_config', jail_config)
        dict.__setattr__(self, 'property_name', property_name)

        if value != "none":
            self.read(value)

    def read(self, config_line):

        ip_addresses = config_line.split(" ")
        for ip_address_string in ip_addresses:

            nic, address = ip_address_string.split("|", maxsplit=1)
            self.add(nic, address)

    def add(self, nic, addresses=[], notify=True):

        if isinstance(addresses, str):
            addresses = [addresses]

        try:
            prop = dict.__getitem__(self, nic)
        except:
            prop = self.__empty_prop(nic)

        for address in addresses:
            prop.add(address, notify=False)

        if notify:
            self.__notify()

    def __setitem__(self, key, values):

        try:
            dict.__delitem__(self, key)
        except:
            pass

        self.add(key, values)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.__notify()

    def __notify(self):
        try:
            self.jail_config.update_special_property(self.property_name)
        except:
            pass

    def __empty_prop(self, key):

        prop = AddressSet(self.jail_config, property_name=self.property_name)
        dict.__setitem__(self, key, prop)
        return prop

    def __reset(self):

        for prop in self:
            pront(f"delete {prop}")

    def __str__(self):
        out = []
        for nic in self:
            for address in self[nic]:
                out.append(f"{nic}|{address}")
        return str(" ".join(out))
