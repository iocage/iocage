.. index:: Known Issues
.. _Known Issues:

Known Issues
============

This section provides a short list of known issues.

.. index:: Known Issues, Mount Path Limit
.. _Mount Path Limit:

Mount Path Limit
----------------

There is a known mountpoint path length limitation issue on FreeBSD.
Path length has an historical 88 character limit.

This issue does not affect :command:`iocage` jails from functioning
properly, but can present challenges when diving into ZFS snapshots,
like :command:`cd` into :file:`.zfs/snapshots`, :command:`tar`, etc.

ZFS snapshot creation and rollback is not affected.

To work around this issue, :command:`iocage` allows the user to
assign and use a unique *NAME* for the jail. Alternately, using the
**[-s | --short]** flag at jail creation tells :command:`iocage` to
assign a shortened UUID to the jail.

.. index:: Known Issues, VNET/VIMAGE
.. _VNETVIMAGE:

VNET/VIMAGE Issues
------------------

VNET/VIMAGE can cause unexpected system crashes when VNET enabled jails
are destroyed. In other words, when the jail process is killed, removed,
or stopped.

As a workaround, :command:`iocage` allows a soft restart without
destroying the jail. :command:`iocage restart -s [UUID | NAME]` executes
a soft restart of the jail.

Example:

:samp:`# iocage restart -s examplejail`

FreeBSD 10.1-RELEASE is stable enough to run with VNET and soft
restarts. There are production machines with :command:`iocage` and VNET
jails running well over 100 days of uptime running both PF and IPFW.

.. index:: Known Issues, VNET and ALTQ
.. _VNETVIMAGE and ALTQ:

VNET/VIMAGE issues w/ ALTQ
++++++++++++++++++++++++++

As recent as FreeBSD 10.1-RELEASE-p10, there are some *interesting*
interactions between VNET/VIMAGE and the ALTernate Queueing (ALTQ)
system used by PF and other routing software. When compiling a kernel,
be sure these lines are **not** in the :file:`kernconf` file (unless
disabling VNET):

.. code-block:: none

 options     ALTQ
 options     ALTQ_CBQ
 options     ALTQ_RED
 options     ALTQ_RIO
 options     ALTQ_HFSC
 options     ALTQ_CDNR
 options     ALTQ_PRIQ

Otherwise, when starting a jail with VNET support enabled, the host
system is likely to crash. Read a more about this issue from a
`2014 mailing list post <http://lists.freebsd.org/pipermail/freebsd-jail/2014-July/002635.html>`_.

.. index:: Known Issues, IPv6 Host Bind Failure
.. _IPv6 Host Bind Failures:

IPv6 host bind failures
-----------------------

In some cases, a jail with an *ip6* address may take too long adding the
address to the interface. Services defined to bind specifically to the
address may then fail. If this happens, add this to :file:`sysctl.conf`
to disable DAD (duplicate address detection) probe packets:

.. code-block:: none

 # disable duplicated address detection probe packets for jails
 net.inet6.ip6.dad_count=0

Adding these lines permanently disables DAD. To set this for ONLY the
current system boot, type :command:`sysctl net.inet6.ip6.dad_count=0` in
a command line interface (CLI). More information about this issue is
available from a
`2013 mailing list post <https://lists.freebsd.org/pipermail/freebsd-jail/2013-July/002347.html>`_.
