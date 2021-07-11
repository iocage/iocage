.. index:: Install iocage
.. _Install iocage:

Install iocage
==============

iocage is a jail and container manager merging some of the best features
and technologies from the FreeBSD operating system. It is geared for
ease of use with simple command syntax. Visit the
`iocage github <https://github.com/iocage/iocage>`_ for more information.

Using binary packages
+++++++++++++++++++++

To install using binary packages on a FreeBSD system, run:

:samp:`sudo pkg install py38-iocage`

Using github
++++++++++++

If installing from github, the FreeBSD source tree **must** be located
at :samp:`$SRC_BASE` ( :samp:`/usr/src` by default).

To install from github, run these commands:

:samp:`pkg install python38 git-lite py38-cython py38-libzfs py38-pip`

:samp:`git clone https://github.com/iocage/iocage`

:samp:`make install` as root.

.. tip:: To install subsequent updates run: :samp:`make install` as
   root.

Using pkg(8)
++++++++++++

It is possible to install pre-build packages using pkg(8) if using
FreeBSD 10 or above.

To install using pkg(8), run:

:samp:`sudo pkg install py38-iocage`

Building Ports
++++++++++++++

iocage is in the FreeBSD ports tree as sysutils/py-iocage.

Build the ports:
:samp:`cd /usr/ports/sysutils/iocage/ ; make install clean`

Upgrading from :samp:`iocage_legacy`
++++++++++++++++++++++++++++++++++++

This repository replaces :samp:`iocage_legacy` .
To upgrade to the current version:

1. Stop the jails ( :samp:`Service iocage stop; iocage stop ALL`)
#. Back up your data.
#. Remove the old :samp:`iocage` package if it is installed
   ( :samp:`pkg delete iocage`)
#. Install :samp:`iocage` using one of the methods above.
#. Migrate the jails by running :samp:`iocage list` as root.
#. Start the jails ( :samp:`service iocage onestart`).

.. index:: Ezjail Migration
.. _Ezjail Migration:

Migrating from Ezjail to Iocage
+++++++++++++++++++++++++++++++

**Assumptions**:

-  ezjail jails are located at ``/usr/jails``
-  iocage jails are located at ``/iocage/jails``

Create Target
-------------

Create an empty jail in iocage to act as the target for the migration.
The release and networking information will be updated with information
from ezjail.

::

    iocage create -e -n NewJail

Copy Old Data
-------------

Before data can be copied, another symlink must be created in the root
directory. Ezjail relies on symlinks to utlilize the basejail system,
however when looking in an existing jail, it’s symlinked to the root.

::

    % ls -ls /usr/jails/OldJail/bin
    1 lrwxr-xr-x  1 root  wheel  13 Feb 22  2017 /usr/jails/OldJail/bin@ -> /basejail/bin

This would work fine from within a running jail, but on the host
filesystem this link doesn’t currently exist. Because of this, create a
symlink from the basejail to the root filesystem of the jail host.

::

    ln -s /usr/jails/basejail /basejail

Now that the link exists, copy the data from the ezjail jail directory
to the iocage jail directory.

::

    rsync -a --copy-links /usr/jails/OldJail/ /iocage/jails/NewJail/root/

Populate iocage config.json
---------------------------

There are 2 main parts from ezjail that need to be copied into the
iocage config:

-  release information
-  IP address

Release
~~~~~~~

The release info can be found in the old basejail files via the
``freebsd-update`` executable.

::

    $ grep USERLAND_VERSION= /usr/jails/basejail/bin/freebsd-version
    USERLAND_VERSION="11.1-RELEASE-p6"

This value goes into the “release” line of ``config.json``

::

    "release": "11.1-RELEASE-p6",

IP Address
~~~~~~~~~~

The IP addresses used in an ezjail jail are found in
``/usr/local/etc/ezjail/OldJail``

::

    $ grep ip= /usr/local/etc/ezjail/OldJail
    export jail_OldJail_ip="em0|192.168.1.10"

This goes into the “ip4_addr” line of ``config.json``

::

    "ip4_addr": "em0|192.168.1.10/24",

Remember to append the subnet mask when adding network info to the
iocage config.

Start the New Jail
~~~~~~~~~~~~~~~~~~

Make sure the old jail is shut down so there won’t be any IP conflicts.

::

    ezjail-admin stop OldJail

Start the new jail with iocage

::

    iocage start NewJail

(Optional) Update fstab
~~~~~~~~~~~~~~~~~~~~~~~

If there are other mounts in use in ezjail, these can be easily copied
into iocage as well.

Ezjail fstab entries are located at ``/etc/fstab.OldJail`` on the host.

::

    $ cat /etc/fstab.OldJail
    /usr/jails/basejail /usr/jails/OldJail/basejail   nullfs   ro   0   0
    /path/on/host /usr/jails/OldJail/path/in/jail   nullfs   rw   0   0

The basejail line isn’t needed in iocage if using the default jail type,
but the remaining entries need to be updated.

Edit the fstab for the iocage jail and change the paths of the
mountpoint.

::

    $ cat /iocage/jails/NewJail/fstab
    /path/on/host /iocage/jails/NewJail/root/path/in/jail   nullfs   rw   0   0
