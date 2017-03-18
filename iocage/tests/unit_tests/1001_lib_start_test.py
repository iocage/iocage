import unittest.mock as mock
import pytest
from iocage.lib.ioc_start import find_bridge_mtu

@mock.patch('iocage.lib.ioc_start.checkoutput')
def test_should_return_mtu_of_first_member(mock_checkoutput):
    mock_checkoutput.side_effect = [bridge_if_config, member_if_config]

    mtu = find_bridge_mtu('bridge0')
    assert mtu == '1500'
    mock_checkoutput.assert_has_calls([mock.call(["ifconfig", "bridge0"]),
                                       mock.call(["ifconfig", "bge0"])])

@mock.patch('iocage.lib.ioc_start.checkoutput')
def test_should_return_mtu_of_first_member_with_description(mock_checkoutput):
    mock_checkoutput.side_effect = [bridge_with_description_if_config,
                                    member_if_config]

    mtu = find_bridge_mtu('bridge0')
    assert mtu == '1500'
    mock_checkoutput.assert_has_calls([mock.call(["ifconfig", "bridge0"]),
                                       mock.call(["ifconfig", "bge0"])])

@mock.patch('iocage.lib.ioc_start.checkoutput')
def test_should_return_default_mtu_if_no_members(mock_checkoutput):
    mock_checkoutput.side_effect = [bridge_with_no_members_if_config,
                                    member_if_config]

    mtu = find_bridge_mtu('bridge0')
    assert mtu == '1500'
    mock_checkoutput.called_with(["ifconfig", "bridge0"])

bridge_if_config = """bridge0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> metric 0 mtu 1500
        ether 00:00:00:00:00:00
        nd6 options=1<PERFORMNUD>
        groups: bridge
        id 00:00:00:00:00:00 priority 32768 hellotime 2 fwddelay 15
        maxage 20 holdcnt 6 proto rstp maxaddr 2000 timeout 1200
        root id 00:00:00:00:00:00 priority 32768 ifcost 0 port 0
            member: bge0 flags=143<LEARNING,DISCOVER,AUTOEDGE,AUTOPTP>
            ifmaxaddr 0 port 1 priority 128 path cost 20000
"""

bridge_with_description_if_config = """bridge0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> metric 0 mtu 1500
        description: first-bridge
        ether 00:00:00:00:00:00
        nd6 options=1<PERFORMNUD>
        groups: bridge
        id 00:00:00:00:00:00 priority 32768 hellotime 2 fwddelay 15
        maxage 20 holdcnt 6 proto rstp maxaddr 2000 timeout 1200
        root id 00:00:00:00:00:00 priority 32768 ifcost 0 port 0
            member: bge0 flags=143<LEARNING,DISCOVER,AUTOEDGE,AUTOPTP>
            ifmaxaddr 0 port 1 priority 128 path cost 20000
"""

bridge_with_no_members_if_config = """bridge0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> metric 0 mtu 1500
        description: first-bridge
        ether 00:00:00:00:00:00
        nd6 options=1<PERFORMNUD>
        groups: bridge
        id 00:00:00:00:00:00 priority 32768 hellotime 2 fwddelay 15
        maxage 20 holdcnt 6 proto rstp maxaddr 2000 timeout 1200
        root id 00:00:00:00:00:00 priority 32768 ifcost 0 port 0
"""

member_if_config = """bge0: flags=8943<UP,BROADCAST,RUNNING,PROMISC,SIMPLEX,MULTICAST> metric 0 mtu 1500
        options=c019b<RXCSUM,TXCSUM,VLAN_MTU,VLAN_HWTAGGING,VLAN_HWCSUM,TSO4,VLAN_HWTSO,LINKSTATE>
        ether 00:00:00:00:00:00
        inet6 fe80::0000:0000:0000:0000%bge0 prefixlen 64 scopeid 0x1
        inet 10.2.3.4 netmask 0xffffff00 broadcast 10.2.3.255
        nd6 options=21<PERFORMNUD,AUTO_LINKLOCAL>
        media: Ethernet autoselect (1000baseT <full-duplex>)
        status: active
"""
