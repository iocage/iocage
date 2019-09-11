.. index:: FAQ
.. _FAQ:

FAQ
===

**What is iocage?**
    :command:`iocage` is a jail management program designed to simplify
    jail administration tasks.

**What is a jail?**
    A *Jail* is a FreeBSD **OS virtualization** technology allowing
    users to run multiple copies of the operating system. Some operating
    systems use the term **Zones** or **Containers** for OS
    virtualization.

**What is VNET?**
    VNET is an independent, per jail virtual networking stack.

**How do I configure network interfaces in a VNET or shared IPjail?**
    Both are configured in the same way:
    :command:`iocage set ip4_add="[interface]|[IP]/[netmask]" [UUID | NAME]`.
    For more info, please refer to the :ref:`Networking` section of this
    documentation.

**Do I need to set my default gateway?**
    Only if VNET is enabled. You need to assign an IP address to the
    **bridge** where the jail interface is attached. This IP essentially
    becomes the default gateway for your jail.

**Can I run a firewall inside a jail?**
    Yes, a VNET jail supports **IPFW**. *PF* is not supported inside the
    jail. However, you can still enable *PF* for the host. If you plan
    to use **IPFW** inside a jail, be sure **securelevel** is set to
    **2**.

**Can I enable both IPFW and PF at the same time?**
    Yes, make sure you allow traffic on both in/out for your jails.

**Can I create custom jail templates?**
    Yes, and thin provisioning is supported too!

**What is a jail clone?**
    **Clones** are ZFS clones. These are fully writable copies of the
    source jail.

**Can I limit the CPU and Memory use?**
    Yes, but **only** for legacy versions of :command:`iocage`. Refer to
    the :file:`iocage.8` manual page or :ref:`Resource Limits` section
    of this documentation for more details.

**Is there a way to display resource consumption?**
    Yes - :command:`iocage df`

**Is NAT supported for jails?**
    Yes. NAT is built into FreeBSD. Treat your server as a core
    router/firewall. Check the FreeBSD
    `Firewalls chapter <https://www.freebsd.org/doc/handbook/firewalls.html>`_
    for more details.

**Will iocage work on a generic system with no ZFS pools?**
    No. ZFS is a must. If you run a FreeBSD server, you should be using
    ZFS!

**Is ZFS jailing supported?**
    Yes, please refer to the :file:`iocage.8` manual page.
