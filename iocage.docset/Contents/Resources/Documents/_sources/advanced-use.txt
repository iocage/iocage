.. index:: Advance Usage
.. _Advanced Usage:

Advanced Usage
==============

.. index:: Clones
.. _Clones:

Clones
------

When a jail is cloned, iocage creates a ZFS clone filesystem.
Essentially, clones are cheap, lightweight, and writable snapshots.

A clone depends on its source snapshot and filesystem. To destroy the
source jail and preserve its clones, the clone must be promoted first.

.. index:: Create clones
.. _Create a Clone:

Create a Clone
++++++++++++++

To clone **www01** to **www02**, run:

:samp:`# iocage clone www01 --name www02`

Clone a jail from an existing snapshot with:

:samp:`# iocage clone www01@snapshotname --name www03`

.. index:: Promote a Clone
.. _Promoting a Clone:

Promoting a Clone
+++++++++++++++++

.. warning:: This functionality isn't fully added to iocage, and may not
   function as expected.

**To promote a cloned jail, run:**

:command:`iocage promote [UUID | NAME]`

This reverses the *clone* and *source* jail relationship. The clone
becomes the source and the source jail is demoted to a clone.

**The demoted jail can now be removed:**

:command:`iocage destroy [UUID | NAME]`

.. index:: Updating Jails
.. _Updating Jails:

Updating Jails
--------------

.. warning:: Updating a basejail is currently not implemented in iocage.
   Refer to iocage
   `GitHub issue #50 <https://github.com/iocage/iocage/issues/50>`_ for
   more information.

Updates are handled with the freebsd-update(8) utility. Jails can be
updated while they are stopped or running. While updating can seem
routine, it is always recommended to use ZFS snapshot functionality to
create a backup of the jail before updating.

Create a backup snapshot of the jail:

:command:`iocage snapshot -n [snapshotname] [UUID | NAME]`

To update a jail to latest patch level, run:

:command:`iocage update [UUID | NAME]`

When updates are finished and the jail appears to function properly,
remove the snapshot:

:command:`iocage snapremove [UUID|NAME]@[snapshotname]`

To test updating without affecting a jail, create a clone and update the
clone the same way as outlined above.

To clone a jail, run:

:command:`iocage clone [UUID|NAME] --name [testupdate]`

.. note:: The **[-n | --name]** flag is optional. :command:`iocage`
   assigns an UUID to the jail if **[-n | --name]** is not used.

.. index:: Upgrade Jails
.. _Upgrading Jails:

Upgrading Jails
---------------

Upgrades are handled with the freebsd-update(8) utility. By default, the
user must supply the new RELEASE for the jail's upgrade. For example:

:samp:`# iocage upgrade examplejail -r 11.0-RELEASE`

Tells jail *examplejail* to upgrade its RELEASE to *11.0-RELEASE*.

Upgrades are handled differently for basejails and the other types of
jails, as a basejail is treated differently in iocage.

.. index:: Upgrade Standard Jail
.. _Upgrade Standard Jail:

Upgrade a Standard Jail
+++++++++++++++++++++++

To upgrade a Standard (non-basejail) jail to the host's RELEASE, run:

:command:`iocage upgrade -r [11.1-RELEASE] [UUID | NAME]`

This upgrades the jail to the same RELEASE as the host.

.. index:: Upgrade Basejail (Legacy)
.. _Upgrade Basejail:

Upgrade basejail (Legacy ONLY)
++++++++++++++++++++++++++++++

.. warning:: This section only applies to **legacy** versions of iocage.
   Basejail upgrade functionality is not yet re-implemented in the
   current version.

Ugrading a basejail has a few steps. Always start by verifying the jail
type, as this process only works with basejails. Running:

:command:`iocage get type [UUID|TAG]`

needs to return **basejail**, for the desired jail.

Upgrading can be forced while the jail is online by executing:

:command:`iocage upgrade [UUID|TAG]`

This forcibly re-clones the basejail filesystems while the jail is
running (no downtime) and update the jail's :file:`/etc` with the
changes from the new RELEASE.

To upgrade the jail while it is stopped, run:

:command:`iocage set release=[11.0-RELEASE] [UUID|TAG]`

This causes the jail to re-clone its filesystems from the *11.0-RELEASE*
on next jail start. This does not update the jail's :file:`/etc` files
with changes from the next RELEASE.

.. index:: Auto-Boot
.. _AutoBoot:

Auto-boot
---------

Make sure :command:`iocage_enable="YES"` is set in :file:`/etc/rc.conf`.

To enable a jail to auto-boot during a system boot, simply run:

:samp:`# iocage set boot=on UUID|NAME`

.. index:: Boot Priority
.. _Boot Priority:

Boot Priority
+++++++++++++

Boot order can be specified by setting the priority value:

:command:`iocage set priority=[20] [UUID|NAME]`

*Lower* values are higher in the boot priority.

.. index:: Snapshot Management
.. _Snapshot Management:

Snapshot Management
-------------------

iocage supports transparent ZFS snapshot management out of the box.
Snapshots are point-in-time copies of data, a safety point to which a
jail can be reverted at any time. Initially, snapshots take up almost no
space, as only changing data is recorded.

List snapshots for a jail:

:command:`iocage snaplist [UUID|NAME]`

Create a new snapshot:

:command:`iocage snapshot [UUID|NAME]`

This creates a snapshot based on the current time.

.. index:: Resource Limits
.. _Resource Limits:

Resource Limits (Legacy ONLY)
-----------------------------

.. warning:: This functionality is only available for legacy versions of
   :command:`iocage`. It is not yet implemented in the current version.
   This applies to all subsections of *Resource Limits*.

:command:`iocage` can enable optional resource limits for a jail. The
outlined procedure here is meant to provide a starting point for the
user.

.. index:: Limit Cores or Threads
.. _Limit Cores or Threads:

Limit Cores or Threads
++++++++++++++++++++++

Limit a jail to a single thread or core #1:

:command:`iocage set cpuset=1 [UUID|TAG]`
:command:`iocage start [UUID|TAG]`

.. index:: List Applied Rules
.. _List Applied Rules:

List Applied Limits
+++++++++++++++++++

List applied limits:

:command:`iocage limits [UUID|TAG]`

.. index:: Limit DRAM Usage
.. _Limit DRAM Usage:

Limit DRAM use
++++++++++++++

This example limits a jail to using 4 Gb DRAM memory (limiting RSS
memory use can be done on-the-fly):

:samp:`# iocage set memoryuse=4G:deny examplejail`

.. index:: Turn on Resource Limits
.. _Turn on Resource Limits:

Turn on Resource Limits
+++++++++++++++++++++++

Turn on resource limiting for a jail with:

:command:`iocage set rlimits=on [UUID|TAG]`

.. index:: Apply Limits
.. _Apply Limits:

Apply limits
++++++++++++

Apply limits to a running jail with:

:command:`iocage cap [UUID | TAG]`

.. index:: Check Limits
.. _Check Limits:

Check Limits
++++++++++++

Check the currently active limits on a jail with:

:command:`iocage limits [UUID | TAG]`

.. index:: Limit CPU Usage by Percentage
.. _Limit CPU Usage by Percentage:

Limit CPU Usage by %
++++++++++++++++++++

In this example, :command:`iocage` limits *testjail* CPU execution to
20%, then applies the limitation to the active jail:

:samp:`# iocage set pcpu=20:deny testjail`
:samp:`# iocage cap testjail`

Double check the jail's current limits to confirm the functionality:

:samp:`# iocage limits testjail`

.. index:: Automatic Package Installation
.. _Automatic Package Installation:

Automatic Package Installation
------------------------------

Packages can be installed automatically at creation time!

Use the [-p | --pkglist] option at creation time, which needs to point
to a JSON file containing one package name per line.

.. note:: An Internet connection is required for automatic package
   installations, as :command:`pkg install` obtains packages from online
   repositories.

Create a :file:`pkgs.json` file and add package names to it.

:file:`pkgs.json`:

.. code-block:: json

   {
       "pkgs": [
       "nginx",
       "tmux"
       ]
   }

Now, create a jail and supply :file:`pkgs.json`:

:command:`iocage create -r [RELEASE] -p [path-to/pkgs.json] -n [NAME]`

.. note:: The **[-n | --name]** flag is optional. :command:`iocage`
   assigns an UUID to the jail if **[-n | --name]** is not used.

This installs **nginx** and **tmux** in the newly created jail.
