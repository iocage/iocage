Known Issues
============

This is a short list of known issues.

88 character mount path limitation
----------------------------------

There is a know mountpoint path length limitation issue on FreeBSD which is set to a historical 88 character limit.

This issue does not affect iocage jails from functioning properly, but can present challenges
when diving into ZFS snapshots (cd into .zfs/snapshots, tar, etc.).

ZFS snapshot creation and rollback is not affected.

To workaround this issue iocage 1.6.0 introduced a ``hack88`` property.

Example:

Shut down jail:

``iocage stop myjail``

Set the ``hack88`` property to "1":

``iocage set hack88=1``

Start jail:

``iocage start myjail``

To revert back to full paths repeat the procedure but set ``hack88=0``.

To create a system wide default (introduced in 1.6.0) for all newly created jails use:

``iocage set hack88=1 default``

Property validation
-------------------

iocage does not validate properties right now. Please refer to man page to see what is supported
for each property. By default iocage pre-configures each property with a safe default.

VNET/VIMAGE issues
------------------

VNET/VIMAGE can cause unexpected system crashes when VNET enabled jails are destroyed - that is when the
jail process is killed, removed, stopped.

As a workaround iocage allows a warm restart without destroying the jail.
By default the restart sub-command will execute a warm restart.

Example:

``iocage restart UUID``

FreeBSD 10.1-RELEASE is stable enough to run with VNET and warm restarts.
There are production machines with iocage and VNET jails running well beyond 100 days of uptime
running both PF and IPFW.

VNET/VIMAGE issues w/ ALTQ
--------------------------

As recent as FreeBSD 10.1-RELEASE-p10, there is some *interesting* interaction between VNET/VIMAGE and ALTQ,
which is an ALTernate Queueing system used by PF and other routing software.  Should you compile a kernel, make
sure that you do not have any of the following lines in your kernconf (unless you want to disable VNET):

::

  options     ALTQ
  options     ALTQ_CBQ
  options     ALTQ_RED
  options     ALTQ_RIO
  options     ALTQ_HFSC
  options     ALTQ_CDNR
  options     ALTQ_PRIQ

Otherwise, should you try to start a jail with VNET support enabled, your host system will more than likely crash.
You can read a little more at the mailing list post `here <http://lists.freebsd.org/pipermail/freebsd-jail/2014-July/002635.html>`_.

IPv6 host bind failures
-----------------------

In some cases a jail with an ip6 address may take too long adding the address
to the interface, and services defined to bind specifically to that address
may fail. In such cases, adding the following sysctl do disable DAD (duplicate
address detection) probe packets.

To set, ``sysctl net.inet6.ip6.dad_count=0``. To make it permanent, add the
setting to sysctl.conf.

::

    # disable duplicated address detection probe packets for jails
    net.inet6.ip6.dad_count=0

You can read a little more about this `here <https://github.com/iocage/iocage/issues/119>`_ and at the mailing list post `here <https://lists.freebsd.org/pipermail/freebsd-jail/2013-July/002347.html>`_.

