.. index:: Create Debian Squeeze Jail
.. _Create a Debian Squeeze Jail:

Create a Debian Squeeze Jail (GNU/kFreeBSD)
===========================================

This section shows the process to set up a Debian (GNU/kFreeBSD) jail.
GNrUkFreeBSD is a Debian userland tailored for the FreeBSD kernel.

The examples in this section use a jail with the custom name
**debjail**. Remember to replace **debjail** with your jail's UUID or
NAME!

.. warning:: This is not recommended for production use. The intention
   is to show :command:`iocage` can do almost anything with jails.

**Create an empty jail with Linux specifics:**

.. code-block:: none

 # iocage create -e -n debjail exec_start="/etc/init.d/rc 3" exec_stop="/etc/init.d/rc 0"

**Install debootstrap on the host:**

:samp:`# pkg install debootstrap`

**Grab the mountpoint for the empty jail, append /root/ to it, and run**
**debootstrap:**

:samp:`# iocage get mountpoint debjail`

:samp:`# debootstrap squeeze /iocage/jails/debjail/root/`

Replace *squeeze* with *wheezy*, if needed.

**Add lines to the jail** :file:`fstab` **file:**

Use :command:`iocage fstab -e [UUID | NAME]` to edit the :file:`fstab`
file of *debjail* directly. Add these lines to the file:

.. code-block:: none

 linsys   /iocage/jails/debjail/root/sys         linsysfs  rw          0 0
 linproc  /iocage/jails/debjail/root/proc        linprocfs rw          0 0
 tmpfs    /iocage/jails/debjail/root/lib/init/rw tmpfs     rw,mode=777 0 0

**Start the jail and attach to it:**

:samp:`# iocage start debjail`

:samp:`# iocage console debjail`

The result is a 64bit Debian Linux userland.

To install a Linux only Debian jail, follow this tutorial:
`debian-linux-freebsd-jail-zfs <http://devil-detail.blogspot.co.nz/2013/08/debian-linux-freebsd-jail-zfs.html>`_
