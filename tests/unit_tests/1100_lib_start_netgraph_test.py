# Copyright (c) 2014-2019, iocage
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
from unittest import mock
import iocage_lib.ioc_start as ioc_start
import subprocess as su

@mock.patch('iocage_lib.ioc_common.checkoutput')
def test_should_return_mtu_of_first_member(mock_checkoutput):
    mock_checkoutput.side_effect = [ng_bridge_info, ng_bridge_show_one_member, ifconfig_member]
    mtu = ioc_start.IOCStart("", "", unit_test=True).find_ng_bridge_mtu('bridge0')
    assert mtu == '9000'
    mock_checkoutput.assert_has_calls([
        mock.call(["ngctl", "info", "bridge0:"], stderr=su.STDOUT),
        mock.call(["ngctl", "show", "bridge0:"], stderr=su.STDOUT),
        mock.call(["ifconfig", "ngeth0"], stderr=su.STDOUT)])

@mock.patch('iocage_lib.ioc_common.checkoutput')
def test_should_return_default_mtu_if_no_members(mock_checkoutput):
    mock_checkoutput.side_effect = [
        su.CalledProcessError(cmd=['ngctl','info','bridge0'],returncode=ng_node_missing_rc,output=ng_node_missing)
    ]

    mtu = ioc_start.IOCStart("", "", unit_test=True).find_ng_bridge_mtu('bridge0')
    assert mtu == '1500'
    mock_checkoutput.assert_has_calls([
        mock.call(["ngctl", "info", "bridge0:"], stderr=su.STDOUT)
    ])

@mock.patch('iocage_lib.ioc_common.checkoutput')
def test_ng_bridge_nextlink_correct(mock_checkoutput):
    side_effects = []
    num_bridge_members = 3
    for i in range(num_bridge_members):
        side_effects.append(ng_bridge_getstats)
                
    side_effects.append(
        su.CalledProcessError(
            cmd=['ngctl','msg','bridge0:', 'getstats', str(num_bridge_members)],
            returncode=ng_node_missing_rc,
            output=ng_bridge_getstats_failure
        )
    )

    mock_checkoutput.side_effect = side_effects

    nextlink = ioc_start.IOCStart("", "", unit_test=True).get_ng_bridge_nextlink('bridge0')
    mock_checkoutput.assert_has_calls([
        mock.call(["ngctl", "msg", "bridge0:", "getstats", str(num_bridge_members)], stderr=su.STDOUT)
    ])
    assert mock_checkoutput.call_count == num_bridge_members+1
    assert nextlink == num_bridge_members

@mock.patch('iocage_lib.ioc_common.checkoutput')
def test_get_ng_nodes_filters_correctly(mock_checkoutput):
    mock_checkoutput.side_effect = [ng_list_many_nodes]
    nodes = ioc_start.IOCStart("", "", unit_test=True).get_ng_nodes(nodetype='bridge')

    mock_checkoutput.assert_has_calls([
        mock.call(["ngctl", "list"], stderr=su.STDOUT),
    ])
    for node in nodes:
        assert node['type'] == 'bridge'

@mock.patch('iocage_lib.ioc_common.checkoutput')
def test_get_ng_nodes_should_be_sorted(mock_checkoutput):
    mock_checkoutput.side_effect = [ng_list_many_nodes]
    nodes = ioc_start.IOCStart("", "", unit_test=True).get_ng_nodes()

    mock_checkoutput.assert_has_calls([
        mock.call(["ngctl", "list"], stderr=su.STDOUT),
    ])
    for i, node in enumerate(nodes[1:]):
        assert int(node['nodeid'],16) > int(nodes[i]['nodeid'],16)

@mock.patch('iocage_lib.ioc_common.checkoutput')
def test_get_ng_bridge_members_should_be_sorted(mock_checkoutput):
    mock_checkoutput.side_effect = [ng_bridge_show_many_members]
    nodes = ioc_start.IOCStart("", "", unit_test=True).get_ng_bridge_members('bridge0')

    mock_checkoutput.assert_has_calls([
        mock.call(["ngctl", "show", "bridge0:"], stderr=su.STDOUT),
    ])
    for i, node in enumerate(nodes[1:]):
        assert int(node['hookindex']) > int(nodes[i]['hookindex'])

ng_bridge_info = """  Name: bridge0         Type: bridge          ID: 00000040   Num hooks: 1
  Local hook      Peer name       Peer type    Peer ID         Peer hook
  ----------      ---------       ---------    -------         ---------
  link0           ngeth0          eiface       00000039        ether
"""

ng_bridge_show_one_member = ng_bridge_info

ng_bridge_getstats = """Rec'd response "getstats" (4) from "[40]:":
Args:   { recvOctets=23741691373 recvPackets=38929211 recvMulticast=27405 recvBroadcast=163203 recvUnknown=12573 xmitOctets=9220089573 xmitPackets=34549262 xmitMulticasts=281 xmitBroadcasts=114523 }
"""
ng_bridge_getstats_failure = b"""ngctl: send msg: Invalid argument
"""

ng_bridge_show_many_members = """  Name: bridge0         Type: bridge          ID: 00000040   Num hooks: 10
  Local hook      Peer name       Peer type    Peer ID         Peer hook
  ----------      ---------       ---------    -------         ---------
  link5           vnet1_38        eiface       000002ed        ether
  link10          vnet0_26        eiface       00000199        ether
  link9           vnet0_25        eiface       00000178        ether
  link8           vnet0_24        eiface       00000159        ether
  link7           vnet0_23        eiface       0000013c        ether
  link6           vnet0_21        eiface       00000104        ether
  link4           vnet0_18        eiface       000000bf        ether
  link3           vnet0_13        eiface       00000056        ether
  link2           vnet0_12        eiface       00000043        ether
  link1           em0             ether        00000001        upper
  link0           em0             ether        00000001        lower
"""

ng_list_many_nodes = """There are 17 total nodes:
  Name: bridge0         Type: bridge          ID: 00000040   Num hooks: 10
  Name: em0             Type: ether           ID: 00000001   Num hooks: 2
  Name: em1             Type: ether           ID: 00000002   Num hooks: 0
  Name: vnet0_12        Type: eiface          ID: 00000043   Num hooks: 1
  Name: vnet0_21        Type: eiface          ID: 00000104   Num hooks: 1
  Name: vnet0_13        Type: eiface          ID: 00000056   Num hooks: 1
  Name: vnet0_24        Type: eiface          ID: 00000159   Num hooks: 1
  Name: vnet0_26        Type: eiface          ID: 00000199   Num hooks: 1
  Name: vnet0_38        Type: eiface          ID: 000002e1   Num hooks: 1
  Name: vnet1_38        Type: eiface          ID: 000002ed   Num hooks: 1
  Name: bridge1         Type: bridge          ID: 000001b2   Num hooks: 3
  Name: ngctl95542      Type: socket          ID: 00000338   Num hooks: 0
  Name: vnet0_25        Type: eiface          ID: 00000178   Num hooks: 1
  Name: ngeth0          Type: eiface          ID: 00000039   Num hooks: 1
  Name: vnet0_23        Type: eiface          ID: 0000013c   Num hooks: 1
  Name: vnet0_18        Type: eiface          ID: 000000bf   Num hooks: 1
"""

# Must be a byte-string, because used to mock raw stderr
ng_node_missing = b"""ngctl: send msg: No such file or directory
"""
ng_node_missing_rc = 71

ifconfig_member = """bge0: flags=8943<UP,BROADCAST,RUNNING,PROMISC,SIMPLEX,MULTICAST> metric 0 mtu 9000
        options=c019b<RXCSUM,TXCSUM,VLAN_MTU,VLAN_HWTAGGING,VLAN_HWCSUM,TSO4,VLAN_HWTSO,LINKSTATE>
        ether 00:00:00:00:00:00
        inet6 fe80::0000:0000:0000:0000%bge0 prefixlen 64 scopeid 0x1
        inet 10.2.3.4 netmask 0xffffff00 broadcast 10.2.3.255
        nd6 options=21<PERFORMNUD,AUTO_LINKLOCAL>
        media: Ethernet autoselect (1000baseT <full-duplex>)
        status: active
"""
