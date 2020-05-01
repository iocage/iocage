.. index:: Networking
.. _Networking:

Networking
==========

Jails have multiple networking options to better serve a user's needs.
Traditionally, jails have only supported IP alias based networking. This
is where an IP address is assigned to the host's interface and then used
by the jail for network communication. This is typically known as
"shared IP" based jails.

Another recently developed option is called VNET or sometimes VIMAGE.
VNET is a fully virtualized networking stack which is isolated per jail.
VNET abstracts virtual network interfaces to jails, which then behave in
the same way as physical interfaces.

By default, iocage does not enable VNET, but users can enable and
configure VNET for a jail by configuring that jail's properties using
the instructions in the :ref:`Configure a Jail` section of this
documentation.

The rest of this section shows more depth of the **Shared IP** and
**VNET** networking options, along with instructions for
:ref:`Configuring Network Interfaces`.

.. warning:: In the examples in this section, **em0** is used as the
   network adapter. **em0** is a placeholder and must be replaced with
   the user's specific network adapter. A network adapter is a computer
   hardware component that connects a computer to a computer network.
   In order to find the network adapter on the system run
   :samp:`ifconfig`.

.. index:: Shared IP
.. _Shared IP:

Shared IP
---------

The *Shared IP* networking option is rock solid, with over a decade of
heavy use and testing.

It has no specific system requirements, as everything needed is built
directly into the default GENERIC kernel.

.. index:: Using Shared IP
.. _Using Shared IP:

Using Shared IP
+++++++++++++++

There are a few steps to follow when setting up *Shared IP*:

**Check the VNET property status**

:samp:`# iocage get vnet examplejail1`

If **vnet** is on, disable it:

:samp:`# iocage set vnet=off examplejail1`

**Configure an IP address**

:samp:`# iocage set ip4_addr="em0|10.1.1.10/24" examplejail1`

If multiple addresses are desired, separate the configuration directives
with a :kbd:`,`:

:samp:`# iocage set ip4_addr="em0|10.1.1.10/24,em0|10.1.1.11/24" examplejail1`

**Start the jail**

:samp:`iocage start examplejail1`

**Verify visible IP configuration in the jail**

:samp:`# iocage exec examplejail1 ifconfig`

.. index:: VIMAGE_VNET
.. _VIMAGEVNET:

VIMAGE/VNET
-----------

VNET is considered experimental. Unexpected system crashes
can occur. More details about issues with VNET are available in the
:ref:`Known Issues` section of this documentation.

There are a number of required steps when configuring a jail to use
VNET:

**Kernel**

.. tip:: If not required, disable SCTP.

Rebuild the kernel with these options:

.. code-block:: none

   nooptions       SCTP   # Stream Control Transmission Protocol
   options         VIMAGE # VNET/Vimage support
   options         RACCT  # Resource containers
   options         RCTL   # same as above

**/etc/rc.conf**

On the host node, add this bridge configuration to :file:`/etc/rc.conf`:

.. code-block:: none

   # set up bridge interface for iocage
   cloned_interfaces="bridge0"

   # plumb interface em0 into bridge0
   ifconfig_bridge0="addm em0 up"
   ifconfig_em0="up"

**/etc/sysctl.conf**

Add these tunables to :file:`/etc/sysctl.conf`:

.. code-block:: none

   net.inet.ip.forwarding=1       # Enable IP forwarding between interfaces
   net.link.bridge.pfil_onlyip=0  # Only pass IP packets when pfil is enabled
   net.link.bridge.pfil_bridge=0  # Packet filter on the bridge interface
   net.link.bridge.pfil_member=0  # Packet filter on the member interface

**Enable vnet for the jail**

:samp:`# iocage set vnet=on examplejail`

**Configure jail's default gateway**

:samp:`# iocage set defaultrouter=10.1.1.254 examplejail`

**Configure an IP address**

:samp:`iocage set ip4_addr="vnet0|10.1.1.10/24" examplejail`

**Start jail and ping the default gateway**

Start the jail:

:samp:`# iocage start examplejail`

Open the system console inside the jail:

:samp:`iocage console examplejail`

Ping the previously configured default gateway:

:samp:`# ping 10.1.1.254`

.. index:: VNET tips
.. _VNET Tips:

Tips
++++

**Routes**

Be sure the default gateway knows the route back to the VNET subnets.

**Using VLANs**

To assign a jail's traffic to a VLAN, add the VLAN interface as a bridge
member, but not the VLAN's parent.  For example:

.. code-block:: none

   sysrc vlans_em0="666"
   sysrc ifconfig_em0_666="up"
   iocage set vnet_default_interface="em0.666" examplejail
   iocage set interfaces="vnet1:bridge1" examplejail


If using VLAN interfaces for the jail host only, on the other hand, add the
parent as a bridge member, but not the VLAN interface.

.. code-block:: none

   sysrc vlans_em0="666"
   sysrc ifconfig_em0_666="1.2.3.4/24"
   iocage set vnet_default_interface="auto" examplejail # "em0" would also work
   iocage set interfaces="vnet1:bridge1" examplejail

.. index:: Configure Network Interfaces
.. _Configuring Network Interfaces:

Configuring Network Interfaces
------------------------------

:command:`iocage` transparently handles network configuration for both
*Shared IP* and *VNET* jails.

.. index:: Configure Shared IP jail
.. _Configuring a Shared IP Jail:

Configuring a Shared IP Jail
++++++++++++++++++++++++++++

**IPv4**

:samp:`# iocage set ip4_addr="em0|192.168.0.10/24" examplejail`

**IPv6**

:samp:`# iocage set ip6_addr="em0|2001:123:456:242::5/64" examplejail`

These examples add IP alias *192.168.0.10/24* and *2001:123:456::5/64*
to interface *em0* of the shared IP jail, at start time.

.. index:: Configure VNET Jail
.. _Configuring a VNET Jail:

Configuring a VNET Jail
+++++++++++++++++++++++

To configure both IPv4 and IPv6:

:samp:`# iocage set ip4_addr="vnet0|192.168.0.10/24" examplejail`

:samp:`# iocage set ip6_addr="vnet0|2001:123:456:242::5/64" examplejail`

:samp:`# iocage set defaultrouter6="2001:123:456:242::1" examplejail`

.. note:: For VNET jails, a default route has to also be specified.

To create a a jail with a DHCP interface add the `dhcp=on` property:

:samp:`# iocage create -r 11.0-RELEASE --name myjail dhcp=on`

The `dhcp=on` property implies creating a VNET virtual network stack and
enabling the Berkley Packet Filter. DHCP cannot work without VNET.
More information about VNET is available in the VNET(9) FreeBSD manual page.

.. index:: Tips for configuring VNET
.. _Tips for Configuring VNET:

Tips for Configuring VNET
+++++++++++++++++++++++++

To start a jail with no IPv4/6 address, **set** the *ip4_addr* and
*ip6_addr* properties, then the *defaultrouter* and *defaultrouter6*
properties:

:samp:`# iocage set ip4_addr=none ip6_addr=none examplejail`

:samp:`# iocage set defaultrouter=none defaultrouter6=none examplejail`

Force iocage to regenerate the MAC and HW address (e.g.: after cloning a jail).  This will cause the MAC and HW addresses to be regenerated when the jail is next started.

:samp:`# iocage set vnet0_mac=none examplejail`
