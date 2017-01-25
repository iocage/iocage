==========
Networking
==========

Intro
------

Jails have multiple networking options based on what features are desired. Traditionally jails
only supported IP alias based networking where an IP address is assigned to the host's interface
which is then utilized by the jail for network communication. This is known as "shared IP" based jails.

Anoter option emerged in recent years, called VNET or sometimes referred to as VIMAGE.
VNET is a fully virtualized, isolated per jail networking stack.
VNET abstracts virtual network interfaces to jails, which behave the same way as physical interfaces.

iocage will try to guess whether VNET support is available in the system and if it is will enable it by
default for newly created jails.

Shared IP
---------

Stability: It is rock solid and battle tested well over a decade.

System requirements
+++++++++++++++++++

None, everything is built into the default GENERIC kernel.

Usage
+++++

**Make sure VNET is disabled**

``iocage get vnet UUID | TAG``

**If set to "on" disable it**

``iocage set vnet=off UUID | TAG``

A system wide default can be configured if required. This will take effect for newly created jails only.

``iocage set vnet=off default``

**Configure an IP address**

``iocage set ip4_addr="em0|10.1.1.10/24" UUID| TAG``

If multiple addresses are desired just separate the configuration directives with a comma.

Example:

``iocage set ip4_addr="em0|10.1.1.10/24,em0|10.1.1.11/24" UUID| TAG``

**Start jail:**

``iocage start UUID | TAG``

**Verify visible IP configuration in the jail**

*(jail must be running for this to work)*

``iocage exec UUID | TAG ifconfig``


VIMAGE/VNET
-----------

Stability: VIMAGE is considered experimental, unexpected system crashes can occur (for details please see known issues section)

System requirements
+++++++++++++++++++

**Kernel**

Rebuild the kernel with the following options:

*(also disable SCTP if not required)*

::

  nooptions       SCTP   # Stream Control Transmission Protocol
  options         VIMAGE # VNET/Vimage support
  options         RACCT  # Resource containers
  options         RCTL   # same as above

**/etc/rc.conf**

Add bridge configuration to /etc/rc.conf:

*(on the host node)*

::

  # set up two bridge interfaces for iocage
  cloned_interfaces="bridge0 bridge1"

  # plumb interface em0 into bridge0
  ifconfig_bridge0="addm em0 up"
  ifconfig_em0="up"

**/etc/sysctl.conf**

Add these tunables to /etc/sysctl.conf:

::

  net.inet.ip.forwarding=1       # Enable IP forwarding between interfaces
  net.link.bridge.pfil_onlyip=0  # Only pass IP packets when pfil is enabled
  net.link.bridge.pfil_bridge=0  # Packet filter on the bridge interface
  net.link.bridge.pfil_member=0  # Packet filter on the member interface

**Configure default GW for jail**

Example: ``iocage set defaultrouter=10.1.1.254 UUID | TAG``

**Configure an IP address**

``iocage set ip4_addr="vnet0|10.1.1.10/24" UUID | TAG``

**Start jail and ping default gateway**

Start the jail:

``iocage start UUID | TAG``

Drop into jail:

``iocage console UUID | TAG``

Ping default gateway, example:

``ping 10.1.1.254``

Gotchas
+++++++

**Routes**

Make sure default gateway knows the route back to the VNET subnets.

**If using VLANs**

If you are using VLAN interfaces for the jail host you not only have
to add the vlan interface as bridge member but the parent interface
of the VLAN as bridge member as well.

Configuring Network Interfaces
------------------------------

iocage handles network configuration for both, shared IP and VNET jails transparently.

Configuring a shared IP jail
++++++++++++++++++++++++++++

**IPv4**

``iocage set ip4_addr="em0|192.168.0.10/24" UUID|TAG``

**IPv6**

``iocage set ip6_addr="em0|2001:123:456:242::5/64" UUID|TAG``

This will add an IP alias 192.168.0.10/24 to interface em0 for the shared IP jail at start time, as well as 2001:123:456::5/64.

Configuring a VNET jail
+++++++++++++++++++++++

To configure both IPv4 and IPv6:

``iocage set ip4_addr="vnet0|192.168.0.10/24" UUID|TAG``

``iocage set ip6_addr="vnet0|2001:123:456:242::5/64" UUID|TAG``

``iocage set defaultrouter6="2001:123:456:242::1" UUID|TAG``

*NOTE: For VNET jails a default route has to be specified too.*

Hints
+++++

To start a jail with no IPv4/6 address whatsoever set these properties:

``iocage set ip4_addr=none ip6_addr=none UUID|TAG``

``iocage set defaultrouter=none defaultrouter6=none UUID|TAG``
