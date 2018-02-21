Migrating from ezjail to iocage
===============================

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
