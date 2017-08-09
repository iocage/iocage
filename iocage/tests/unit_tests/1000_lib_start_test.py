# Copyright (c) 2014-2017, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
import mock
import iocage.lib.ioc_start as ioc_start


@mock.patch('iocage.lib.ioc_common.checkoutput')
def test_should_return_mtu_of_first_member(mock_checkoutput):
    mock_checkoutput.side_effect = [bridge_if_config, member_if_config]

    mtu = ioc_start.IOCStart("", "", "").find_bridge_mtu('bridge0')
    assert mtu == '1500'
    mock_checkoutput.assert_has_calls([mock.call(["ifconfig", "bridge0"]),
                                       mock.call(["ifconfig", "bge0"])])


@mock.patch('iocage.lib.ioc_common.checkoutput')
def test_should_return_mtu_of_first_member_with_description(mock_checkoutput):
    mock_checkoutput.side_effect = [bridge_with_description_if_config,
                                    member_if_config]

    mtu = ioc_start.IOCStart("", "", "").find_bridge_mtu('bridge0')
    assert mtu == '1500'
    mock_checkoutput.assert_has_calls([mock.call(["ifconfig", "bridge0"]),
                                       mock.call(["ifconfig", "bge0"])])


@mock.patch('iocage.lib.ioc_common.checkoutput')
def test_should_return_default_mtu_if_no_members(mock_checkoutput):
    mock_checkoutput.side_effect = [bridge_with_no_members_if_config,
                                    member_if_config]

    mtu = ioc_start.IOCStart("", "", "").find_bridge_mtu('bridge0')
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
