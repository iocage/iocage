from unittest.mock import Mock, patch

from iocage_lib.ioc_json import IOCJson


def test_01_ip4_addr():
    IOCJson.validate_ip4_addr('192.0.0.1')

def test_02_ip4_net():
    IOCJson.validate_ip4_addr('192.0.0.1/24')

def test_03_ip4_ptp():
    IOCJson.validate_ip4_addr('192.0.0.100/32 192.0.0.1')

def test_04_ip6_addr():
    IOCJson.validate_ip6_addr('1:2:3:4::')

def test_05_ip6_ptp():
    IOCJson.validate_ip6_addr('1:2:3:4::/128 1:2:3:4::1')

def test_06_ip6_net():
    IOCJson.validate_ip6_addr('1:2:3:4::/64')
