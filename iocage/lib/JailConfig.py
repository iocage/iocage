import re

import JailConfigJSON
import JailConfigInterfaces
import JailConfigAddresses
import JailConfigResolver
import JailConfigFstab
import JailConfigLegacy
import JailConfigZFS
import helpers


class JailConfig():

    def __init__(self, data={}, jail=None, logger=None, new=False):

        helpers.init_logger(self, logger)

        object.__setattr__(self, 'data', {})
        object.__setattr__(self, 'special_properties', {})
        object.__setattr__(self, 'legacy', False)

        # jail is required for various operations (write, fstab, etc)
        if jail:
            object.__setattr__(self, 'jail', jail)
            fstab = JailConfigFstab.JailConfigFstab(
                jail=jail, logger=self.logger)
            object.__setattr__(self, 'fstab', fstab)
        else:
            self.jail = None
            self.fstab = None

        data_keys = data.keys()

        # the UUID is used in many other variables and needs to be set first
        if "name" in data_keys:
            self.name = data["name"]
        elif "uuid" in data_keys:
            self.name = data["uuid"]
        else:
            object.__setattr__(self, 'id', None)

        # be aware of iocage-legacy jails for migration
        try:
            self.legacy = data.legacy is True
        except:
            self.legacy = False

        self.clone(data)

    def clone(self, data):
        for key in data:
            self.__setattr__(key, data[key])

    def read(self):

        try:
            JailConfigJSON.JailConfigJSON.read(self)
            object.__setattr__(self, 'legacy', False)
            self.logger.log("Configuration loaded from JSON", level="verbose")
            return
        except:
            pass

        try:
            JailConfigLegacy.JailConfigLegacy.read(self)
            object.__setattr__(self, 'legacy', True)
            self.logger.verbose(
                "Configuration loaded from UCL config file (iocage-legacy)")
            return
        except:
            pass

        try:
            JailConfigZFS.JailConfigZFS.read(self)
            object.__setattr__(self, 'legacy', True)
            self.logger.verbose(
                "Configuration loaded from ZFS properties (iocage-legacy)")
            return
        except:
            pass

        self.logger.debug("No configuration was found")

    def update_special_property(self, name, new_property_handler=None):

        try:
            if new_property_handler is not None:
                self.special_properties[name] = new_property_handler

            self.data[name] = str(self.special_properties[name])
        except:
            # pass when there is no handler for the notifying propery
            pass

    def save(self):
        if not self.legacy:
            self.save_json()
        else:
            JailConfigLegacy.JailConfigLegacy.save(self)

    def save_json(self):
        JailConfigJSON.JailConfigJSON.save(self)

    def _set_name(self, name):

        try:
            # We do not want to set the same name twice.
            # This can occur when the Jail is initialized
            # with it's name and the same name is read from
            # the configuration
            if self.id == name:
                return
        except:
            pass

        allowed_characters_pattern = "([^A-z0-9\\._\\-]|\\^)"
        invalid_characters = re.findall(allowed_characters_pattern, name)
        if len(invalid_characters) > 0:
            msg = (
                f"Invalid character in name: "
                " ".join(invalid_characters)
            )
            self.logger.error(msg)

        name_pattern = f"^[A-z0-9]([A-z0-9\\._\\-]+[A-z0-9])*$"
        if not re.match(name_pattern, name):
            msg = f"Names have to begin and end with an alphanumeric character"
            self.logger.error(msg)
            raise Exception(msg)

        self.__setattr__("id", name)

        try:
            self.host_hostname
        except:
            self.host_hostname = name

        self.logger.spam(
            f"Set jail name to {name}",
            jail=self.jail
        )

    def _get_type(self):

        # ToDo: Implement template jails or remove
        current_type = None
        try:
            if (self.data["type"] == "jail") or (self.data["type"] == ""):
                current_type = "jail"
        except:
            current_type = "jail"

        if current_type == "jail":
            if self.basejail:
                return "basejail"
            elif self.clonejail:
                return "clonejail"
            else:
                return "jail"

        return self.data["type"]

    def _set_type(self, value):

        if value == "basejail":
            self.basejail = True
            self.clonejail = False
            self.data["type"] = "jail"

        elif value == "clonejail":
            self.basejail = False
            self.clonejail = True
            self.data["type"] = "jail"

        else:
            self.data["type"] = value

    def _get_basejail(self):
        value = self.data["basejail"]
        return (value == "on") or (value == "yes")

    def _default_basejail(self):
        return False

    def _set_basejail(self, value):
        enabled = (value is True) or (value == "on") or (value == "yes")
        if self.legacy:
            self.data["basejail"] = "on" if enabled else "off"
        else:
            self.data["basejail"] = "yes" if enabled else "no"

    def _get_clonejail(self):
        return self.data["clonejail"] == "on"

    def _default_clonejail(self):
        return True

    def _set_clonejail(self, value):
        self.data["clonejail"] = "on" if (
            value is True) or (value == "on") else "off"

    def _get_ip4_addr(self):
        try:
            return self.special_properties["ip4_addr"]
        except:
            return None

    def _set_ip4_addr(self, value):
        ip4_addr = JailConfigAddresses.JailConfigAddresses(
            value,
            jail_config=self,
            property_name="ip4_addr"
        )
        self.special_properties["ip4_addr"] = ip4_addr
        self.update_special_property("ip4_addr")

    def _get_ip6_addr(self):
        try:
            return self.special_properties["ip6_addr"]
        except:
            return None

    def _set_ip6_addr(self, value):
        ip6_addr = JailConfigAddresses.JailConfigAddresses(
            value,
            jail_config=self,
            property_name="ip6_addr"
        )
        self.special_properties["ip6_addr"] = ip6_addr
        self.update_special_property("ip6_addr")

    def _get_interfaces(self):
        return self.special_properties["interfaces"]

    def _set_interfaces(self, value):
        interfaces = JailConfigInterfaces.JailConfigInterfaces(
            value,
            jail_config=self
        )
        self.special_properties["interfaces"] = interfaces
        self.update_special_property("interfaces")

    def _get_defaultrouter(self):
        value = self.data['defaultrouter']
        return value if (value != "none" and value is not None) else None

    def _set_defaultrouter(self, value):
        if value is None:
            value = 'none'
        self.data['defaultrouter'] = value

    def _default_defaultrouter(self):
        return None

    def _get_defaultrouter6(self):
        value = self.data['defaultrouter6']
        return value if (value != "none" and value is not None) else None

    def _set_defaultrouter6(self, value):
        if value is None:
            value = 'none'
        self.data['defaultrouter6'] = value

    def _default_defaultrouter6(self):
        return None

    def _get_vnet(self):
        return self.data["vnet"] == "on"

    def _set_vnet(self, value):
        vnet_enabled = (value == "on") or (value is True)
        self.data["vnet"] = "on" if vnet_enabled else "off"

    def _get_jail_zfs_dataset(self):
        try:
            return self.data["jail_zfs_dataset"].split()
        except:
            pass
        return []

    def _set_jail_zfs_dataset(self, value):
        value = [value] if isinstance(value, str) else value
        self.data["jail_zfs_dataset"] = " ".join(value)

    def _get_jail_zfs(self):
        enabled = self.data["jail_zfs"] == "on"
        if not enabled:
            if len(self.jail_zfs_dataset) > 0:
                raise Exception(
                    "jail_zfs is disabled"
                    "despite jail_zfs_dataset is configured"
                )
        return enabled

    def _set_jail_zfs(self, value):
        if (value is None) or (value == ""):
            del self.data["jail_zfs"]
            return
        enabled = (value == "on") or (value is True)
        self.data["jail_zfs"] = "on" if enabled else "off"

    def _default_jail_zfs(self):
        # if self.data["jail_zfs"] does not explicitly exist, _get_jail_zfs
        # would raise
        try:
            return len(self.jail_zfs_dataset) > 0
        except:
            return False

    def _default_mac_prefix(self):
        return "02ff60"

    def _get_resolver(self):
        return self.__create_special_property_resolver()

    def _set_resolver(self, value):

        if isinstance(value, str):
            self.data["resolver"] = value
            resolver = self.resolver
        else:
            resolver = JailConfigResolver.JailConfigResolver(
                jail_config=self)
            resolver.update(value, notify=True)

    def _get_cloned_release(self):
        try:
            return self.data["cloned_release"]
        except:
            return self.release

    def _get_basejail_type(self):
        return self.data["basejail_type"]

    def _default_basejail_type(self):
        try:
            if self.basejail:
                return "nullfs"
        except:
            pass
        return None

    def _get_login_flags(self):
        return JailConfigList(self.data["login_flags"].split())

    def _set_login_flags(self, value):
        if value is None:
            try:
                del self.data["login_flags"]
            except:
                pass
        else:
            if isinstance(value, list):
                self.data["login_flags"] = " ".join(value)
            elif isinstance(value, str):
                self.data["login_flags"] = value
            else:
                raise Exception("Invalid login_flags")

    def _set_tags(self, value):
        if isinstance(value, str):
            self.tags = value.split(",")
        elif isinstance(value, list):
            self.tags = set(value)
        elif isinstance(value, set):
            self.tags = value
        else:
            raise Exception("Invalid tags")

    def _default_login_flags(self):
        return JailConfigList(["-f", "root"])

    def _default_vnet(self):
        return False

    def _default_ip4_saddrsel(self):
        return 1

    def _default_ip6_saddrsel(self):
        return 1

    def _default_ip4(self):
        return "new"

    def _default_ip6(self):
        return "new"

    def _default_host_hostname(self):
        return self.jail.humanreadable_name

    def _default_host_hostuuid(self):
        return self.id

    def _default_host_domainname(self):
        return "none"

    def _default_devfs_ruleset(self):
        return "4"

    def _default_enforce_statfs(self):
        return "2"

    def _default_children_max(self):
        return "0"

    def _default_allow_set_hostname(self):
        return "1"

    def _default_allow_sysvipc(self):
        return "0"

    def _default_allow_raw_sockets(self):
        return "0"

    def _default_allow_chflags(self):
        return "0"

    def _default_allow_mount(self):
        return "0"

    def _default_allow_mount_devfs(self):
        return "0"

    def _default_allow_mount_nullfs(self):
        return "0"

    def _default_allow_mount_procfs(self):
        return "0"

    def _default_allow_mount_zfs(self):
        return "0"

    def _default_allow_mount_tmpfs(self):
        return "0"

    def _default_allow_quotas(self):
        return "0"

    def _default_allow_socket_af(self):
        return "0"

    def _default_sysvmsg(self):
        return "new"

    def _default_sysvsem(self):
        return "new"

    def _default_sysvshm(self):
        return "new"

    def _default_exec_clean(self):
        return "1"

    def _default_exec_fib(self):
        return "0"

    def _default_exec_prestart(self):
        return "/usr/bin/true"

    def _default_exec_start(self):
        return "/bin/sh /etc/rc"

    def _default_exec_poststart(self):
        return "/usr/bin/true"

    def _default_exec_prestop(self):
        return "/usr/bin/true"

    def _default_exec_stop(self):
        return "/bin/sh /etc/rc.shutdown"

    def _default_exec_poststop(self):
        return "/usr/bin/true"

    def _default_exec_timeout(self):
        return "60"

    def _default_stop_timeout(self):
        return "30"

    def _default_mount_devfs(self):
        return "1"

    def _default_mount_fdescfs(self):
        return "1"

    def _default_securelevel(self):
        return "2"

    def _default_tags(self):
        return []

    def __create_special_property_resolver(self):

        create_new = False
        try:
            self.special_properties["resolver"]
        except:
            create_new = True
            pass

        if create_new:
            resolver = JailConfigResolver.JailConfigResolver(
                jail_config=self, logger=self.logger)
            resolver.update(notify=False)
            self.special_properties["resolver"] = resolver

        return self.special_properties["resolver"]

    def __getattr__(self, key, string=False):

        # passthrough existing properties
        try:
            return self.stringify(self.__getattribute__(key), string)
        except:
            pass

        # data with mappings
        get_method = None
        try:
            get_method = self.__getattribute__(f"_get_{key}")
            return self.stringify(get_method(), string)
        except:
            pass

        # plain data attribute
        try:
            return self.stringify(self.data[key], string)
        except:
            pass

        # then fall back to default
        try:
            fallback_method = self.__getattribute__(f"_default_{key}")
            return self.stringify(fallback_method(), string)
        except:
            raise Exception(f"Variable {key} not found")

    def __delattr__(self, key):
        del self.data[key]

    def __setattr__(self, key, value):

        # passthrough existing properties
        try:
            self.__getattribute__(key)
            object.__setattr__(self, key, value)
            return
        except:
            pass

        setter_method = None
        try:
            setter_method = self.__getattribute__(f"_set_{key}")
        except:
            self.data[key] = value
            pass

        if setter_method is not None:
            return setter_method(value)

    def __str__(self):
        return JailConfigJSON.JailConfigJSON.toJSON(self)

    def __dir__(self):

        properties = set()

        for prop in dict.__dir__(self):
            if prop.startswith("_default_"):
                properties.add(prop[9:])
            elif not prop.startswith("_"):
                properties.add(prop)

        for key in self.data.keys():
            properties.add(key)

        return list(properties)

    @property
    def all_properties(self):

        properties = set()

        for prop in dict.__dir__(self):
            if prop.startswith("_default_"):
                properties.add(prop[9:])

        for key in self.data.keys():
            properties.add(key)

        return list(properties)

    def stringify(self, value, enabled=True):

        if not enabled:
            return value
        elif value is None:
            return "-"
        elif value is True:
            return "on"
        elif value is False:
            return "off"
        else:
            return str(value)


class JailConfigList(list):

    def __str__(self):
        return " ".join(self)
