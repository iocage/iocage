FAQ
===

**What is iocage?**
    iocage is jail management script aiming to simplify jail administration
    tasks as much as possible.

**What is a jail?**
    Jail is a FreeBSD **OS virtualization** technology allowing to run multiple
    copies of the operating system. Some operating systems use the term
    **Zones** or **Containers** for OS virtualization.

**What is VNET?**
    VNET is an independent per jail virtual networking stack.

**How do I configure network interfaces in a VNET or shared IPjail?**
    You configure both the same way: ``iocage set
    ip4_add="interface|IP/netmask" UUID | TAG``. For more info please refer to the
    documentation.

**Do I need to set my default gateway?**
    Only if VNET is enabled. You need to assign an IP address to the **bridge**
    where the jail interface is attached to. This IP essentially becomes your default
    gateway for your jail.
 
**Can I run a firewall inside a jail?**
    Yes in a VNET jail **IPFW is supported**. PF is not supported inside the
    jail - though you can still enable PF for the host itself. If you plan on
    using **IPFW** inside a jail make sure **securelevel** is set to **2**

**Can I enable both IPFW and PF at the same time?**
    Yes, make sure you allow traffic on both in/out for your jails.

**Can I create custom jail templates?**
    Yes, and thin provision them too! Starting with version 1.3 there is also a
    package option for jail packaging.

**What is a jail clone?**
    **Clones** are ZFS clones, these are fully writable copies of the
    source jail.

**Can I limit the CPU and Memory use?**
    Yes. (refer to manual page)

**Is there a way to display resource consumption?**
    Yes, ``iocage inuse UUID | TAG``

**Is NAT supported for the jails?**
    Yes. This is built into FreeBSD. Treat your server as a core
    router/firewall. Check documentation section on NAT.

**Will iocage work on a generic system with no ZFS pools?**
    No. ZFS is a must, if you run a FreeBSD server you should be using ZFS!

**Is ZFS jailing supported?**
    Yes, please refer to man page.
