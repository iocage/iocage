==============
Advanced usage
==============

Clones
------

When a jail is cloned, iocage creates a ZFS clone filesystem.
Essentially, clones are cheap, lightweight, and writable snapshots.

A clone depends on its source snapshot and filesystem. To destroy the
source jail and preserve its clones, the clone must be promoted first.

Create a clone
++++++++++++++

To clone **www01** to **www02**, run:

:samp:`# iocage clone www01 tag=www02`

Clone a jail from an existing snapshot with:

:samp:`# iocage clone www01@snapshotname tag=www03`

Promoting a clone
+++++++++++++++++

**To promote a cloned jail, run:**

:samp:`# iocage promote UUID | TAG`

This reverses the *clone* and *source* jail relationship. The clone
becomes the source and the source jail is demoted to a clone.

**The demoted jail can now be removed:**

:samp:`# iocage destroy UUID | TAG`

Updating jails
--------------

Updates are handled with the freebsd-update(8) utility. Jails can be
updated while they are stopped or running.

To update a jail to latest patch level, run:

:samp:`# iocage update UUID | TAG`

This automatically creates a back-out snapshot of the jail.

When updates are finished and the jail appears to function properly,
remove the snapshot:

:samp:`# iocage snapremove UUID|TAG@snapshotname`

If the update breaks the jail, revert back to the original snapshot:

:samp:`# iocage rollback UUID|TAG@snapshotname`

To test updating without affecting a jail, create a clone and update the
clone the same way as outlined above.

To clone a jail, run:

:samp:`# iocage clone UUID|TAG tag=testupdate`

Upgrading jails
---------------

Upgrades are handled with the freebsd-update(8) utility. By default, the
upgrade command attempts to upgrade the jail to the host's RELEASE
version (visible with uname -r).

Based on the jail **type** property, upgrades are handled differently
for basejails and normal jails.

Upgrade Normal Jails
++++++++++++++++++++

To upgrade a normal jail (non-basejail) to the host's RELEASE, run:

:samp:`# iocage upgrade UUID | TAG`

This upgrades the jail to the same RELEASE as the host.

To upgrade to a specific release, run:

:samp:`# iocage upgrade UUID|TAG release=10.1-RELEASE`

Upgrade basejail
++++++++++++++++

Ugrading a basejail has a few steps. Always start by verifying the jail
type, as this process only works with basejails. Running:

:samp:`# iocage get type UUID|TAG`

needs to return "basejail", for the desired jail.

Upgrading can be forced while the jail is online by executing:

:samp:`# iocage upgrade UUID|TAG`

This forcibly re-clones the basejail filesystems while the jail is
running (no downtime) and update the jail's :file:`/etc` with the
changes from the new RELEASE.

To upgrade the jail while it is stopped, run:

:samp:`# iocage set release=11.0-RELEASE UUID|TAG`

This causes the jail to re-clone its filesystems from the 11.0-RELEASE
on next jail start. This does not update the jail's :file:`/etc` files
with changes from the next RELEASE.

Auto boot
---------

Make sure :command:`iocage_enable="YES"` is set in :file:`/etc/rc.conf`.

To enable a jail to auto-boot during a system boot, simply run:

:samp:`# iocage set boot=on UUID|TAG`

Boot priority
+++++++++++++

Boot order can be specified by setting the priority value:

:samp:`# iocage set priority=20 UUID|TAG`

*Lower* values are higher in the boot priority.

Snapshot management
-------------------

iocage supports transparent ZFS snapshot management out of the box.
Snapshots are point-in-time copies of data, a safety point to which a
jail can be reverted at any time. Initially, snapshots take up almost no
space, as only changing data is recorded.

List snapshots for a jail with:

:samp:`# iocage snaplist UUID|TAG`

To create a new snapshot, run:

:samp:`# iocage snapshot UUID|TAG`

This creates a snapshot based on current time.

To create a snapshot with custom naming, run:

:samp:`# iocage snapshot UUID|TAG@mysnapshotname`

Resource limits
---------------

iocage can enable optional resource limits for a jail. The outlined
procedure here is meant to provide a starting point for the user.

Limit core or thread
++++++++++++++++++++

Limit a jail to a single thread or core number 1:

:samp:`# iocage set cpuset=1 UUID|TAG`
:samp:`# iocage start UUID|TAG`

List applied rules
++++++++++++++++++

List applied limits:

:samp:`# iocage limits UUID|TAG`

Limit DRAM use
++++++++++++++

Limit a jail to 4G DRAM memory use (limit RSS memory use can be done
on-the-fly):

:samp:`# iocage set memoryuse=4G:deny UUID|TAG`

Turn on resource limits
+++++++++++++++++++++++

Turn on resource limiting for jail:

:samp:`# iocage set rlimits=on UUID|TAG`

Apply limits
++++++++++++

Apply limit on-the-fly:

:samp:`# iocage cap UUID | TAG`

Check limits
++++++++++++

Check active limits:

:samp:`# iocage limits UUID | TAG`

Limit CPU use by %
++++++++++++++++++

Limit CPU execution to 20%:

:samp:`# iocage set pcpu=20:deny UUID|TAG`
:samp:`# iocage cap UUID|TAG`

Check limits:

:samp:`# iocage limits UUID | TAG`

Resetting a jail's properties
+++++++++++++++++++++++++++++

iocage easily allows resetting a jail's properties back to their
defaults!

To reset to defaults:

:samp:`# iocage reset UUID | TAG`

You can also reset every jail to the default properties:

:samp:`# iocage reset ALL`

Resetting a jail retains the jail's UUID and TAG. Everything else is
lost. Be sure to reset any needed custom properties. If anything is set
by ``iocage set PROPERTY default``, there is nothing else required!

Automatic package installation
------------------------------

Packages can be installed automatically at creation time!

Specify the ``pkglist`` property at creation time, which needs to point
to a text file containing one package name per line. Note an Internet
connection is required, as :command:`pkg install` obtains packages from
online repositories.

**Example:**

Create a :file:`pkgs.txt` file and add package names to it.

:file:`pkgs.txt`:

.. code-block:: none

   nginx
   tmux

Now, create a jail and supply :file:`pkgs.txt`:

:samp:`# iocage create pkglist=/path-to/pkgs.txt tag=myjail`

This installs **nginx** and **tmux** in the newly created jail.
