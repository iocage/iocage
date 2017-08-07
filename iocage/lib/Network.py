import NetworkInterface
import helpers

import subprocess
from hashlib import md5


class Network:

    def __init__(self, jail,
                 nic="vnet0",
                 ipv4_addresses=[],
                 ipv6_addresses=[],
                 mtu=1500,
                 bridges=None,
                 logger=None):

        helpers.init_logger(self, logger)

        if bridges is not None:
            if not isinstance(bridges, list):
                raise Exception(
                    "Invalid parameter bridges: "
                    "None or List of Strings expected"
                )

        self.vnet = True
        self.bridges = bridges
        self.jail = jail
        self.nic = nic
        self.mtu = mtu
        self.ipv4_addresses = ipv4_addresses
        self.ipv6_addresses = ipv6_addresses

    def setup(self):
        if self.vnet:
            if not self.bridges or len(self.bridges) == 0:
                raise Exception(
                    "VNET is enabled and requires setting a bridge")

            jail_if, host_if = self.__create_vnet_iface()

    def teardown(self):
        if self.vnet:
            # down host_if
            NetworkInterface.NetworkInterface(
                name=self.nic_local_name,
                extra_settings=["down"],
                logger=self.logger
            )

    @property
    def nic_local_name(self):
        self.jail.require_jail_running()

        return f"{self.nic}:{self.jail.jid}"

    @property
    def nic_local_description(self):
        return f"associated with jail: {self.jail.humanreadable_name}"

    def __create_vnet_iface(self):

        # create new epair interface
        epair_a_cmd = ["ifconfig", "epair", "create"]
        epair_a = subprocess.Popen(
            epair_a_cmd, stdout=subprocess.PIPE, shell=False).communicate()[0]
        epair_a = epair_a.decode("utf-8").strip()
        epair_b = f"{epair_a[:-1]}b"

        mac_a, mac_b = self.__generate_mac_address_pair()

        host_if = NetworkInterface.NetworkInterface(
            name=epair_a,
            mac=mac_a,
            mtu=self.mtu,
            description=self.nic_local_description,
            rename=self.nic_local_name,
            logger=self.logger
        )

        # add host_if to bridges
        for bridge in self.bridges:
            NetworkInterface.NetworkInterface(
                name=bridge,
                addm=self.nic_local_name,
                extra_settings=["up"],
                logger=self.logger
            )

        # up host_if
        NetworkInterface.NetworkInterface(
            name=self.nic_local_name,
            extra_settings=["up"],
            logger=self.logger
        )

        # assign epair_b to jail
        self.__assign_vnet_iface_to_jail(epair_b, self.jail.identifier)

        jail_if = NetworkInterface.NetworkInterface(
            name=epair_b,
            mac=mac_b,
            mtu=self.mtu,
            rename=self.nic,
            jail=self.jail,
            extra_settings=["up"],
            ipv4_addresses=self.ipv4_addresses,
            ipv6_addresses=self.ipv6_addresses,
            logger=self.logger
        )

        return jail_if, host_if

    def __assign_vnet_iface_to_jail(self, nic, jail_name):
        NetworkInterface.NetworkInterface(
            name=nic,
            vnet=jail_name,
            logger=self.logger
        )

    def __generate_mac_bytes(self):
        m = md5()
        m.update(self.jail.id.encode("utf-8"))
        m.update(self.nic.encode("utf-8"))
        prefix = self.jail.config.mac_prefix
        return f"{prefix}{m.hexdigest()[0:12-len(prefix)]}"

    def __generate_mac_address_pair(self):
        mac_a = self.__generate_mac_bytes()
        mac_b = hex(int(mac_a, 16) + 1)[2:].zfill(12)
        return mac_a, mac_b
