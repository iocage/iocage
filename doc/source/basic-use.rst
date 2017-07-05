.. index:: Basic Usage
.. _Basic Usage:

Basic Usage
===========

This section is about basic iocage usage and is meant as a "how-to"
reference for new users.

.. tip:: Remember, command line help is always available by typing
   :command:`iocage --help` or :command:`iocage [subcommand] --help`.

iocage has a basic "flow" when first used. As a new user interacts with
iocage for the first time, this flow guides them through initializing
iocage, then interacting with newly created jails.

.. index:: Activate iocage
.. _Activate iocage:

Activate iocage
---------------

Before iocage is functional, it needs to :command:`activate`.
Essentially, iocage needs to link with a usable zpool. In most cases,
activation is automatic to the primary system zpool, but more advanced
users can use :command:`iocage activate` to designate a different zpool
for iocage usage.

Once iocage is ready with an active zpool, users are able to immediately
begin downloading FreeBSD releases for jail creation.

.. index:: Fetch a release
.. _Fetch a Release:

Fetch a Release
---------------

iocage now needs to fetch a RELEASE, which is used to create jails. By
default, typing :command:`iocage fetch` opens a menu for the user to
choose which release to download, as seen in this example:

.. code-block:: none

 # iocage fetch
 [0] 9.3-RELEASE (EOL)
 [1] 10.1-RELEASE (EOL)
 [2] 10.2-RELEASE (EOL)
 [3] 10.3-RELEASE
 [4] 11.0-RELEASE

 Type the number of the desired RELEASE
 Press [Enter] to fetch the default selection: (default)
 Type EXIT to quit: 4

Once the desired RELEASE is downloaded, the most recent patches are also
applied to it.

:command:`iocage fetch` also has a number of options and properties for
users to fine-tune the functionality of the command.

If a specific RELEASE is required, type:

:samp:`# iocage fetch release=10.3-RELEASE`

If a specific download mirror is required, type:

:samp:`# iocage fetch ftphost=ftp.hostname.org`

:command:`fetch` can also pull from a specific ftp directory:

:samp:`# iocage fetch ftpdir=/dir/`

.. index:: Basic Jail Creation
.. _Create a Jail:

Create a Jail
-------------

With a release downloaded, iocage is now able to create jails. There are
five types of jails, three basic and two advanced. Basic jail types are
**full**, **clone**, and **base** jails. Advanced jails types are
**empty** and **templates**, but these are discussed in the
:ref:`Jail Types` section, along with more detailed descriptions of the
basic jail types.

Depending on the user's requirements, the :command:`create` subcommand
can be tweaked to create any of the three basic types. By default,
iocage creates a fully independent jail of the current host's RELEASE,
setting the TAG property to the current date.

The :command:`create` command can be used to quickly create a basic
jail:

:samp:`# iocage create -r 11.0-RELEASE`

This basic jail is fully independent.

To create a full jails with multiple clones, type:

:samp:`# iocage create -r 11.0-RELEASE -c 2`

The numeric value after the **-c** flag is used to designate the number
of clone jails to create. In the above example, *two* jails are created,
**one** *full* jail and **one** clone jail.

A simple basejail is created with the **-b** flag:

:samp:`# iocage create -b -r 11.0-RELEASE`

After designating the type of jail to create with the option flags,
specific jail **properties** can also be set. For example:

:samp:`# iocage create -r 11.0-RELEASE tag=myjail boot=on`

Creates a FreeBSD 11.0 jail with the custom tag *myjail* and sets the
jail to start at system boot time.

More information about iocage jail properties is available in the
iocage(8) FreeBSD manual page, which is accessed on a FreeBSD system by
typing :command:`man iocage`.

.. index:: Listing Jails
.. _Listing Jails:

Listing Jails
-------------

To list all jails:

:samp:`# iocage list`

To see all downloaded RELEASEs:

:samp:`# iocage list -r`

View available templates with:

:samp:`# iocage list -t`

.. index:: Jail start stop restart
.. _Start Stop Restart Jail:

Start, Stop, or Restart a Jail
------------------------------

Jails can be started, stopped, or restarted at any time with iocage. By
default, new jails are in a *down* (stopped) state. To see the status of
all jails, use :command:`iocage list` and read the **STATE** column.

Use each jail's UUID or custom TAG to start, stop, or restart it. When
using a jail's UUID, it is not required to type the full UUID. Partial
UUIDs are acceptable, as long as the given characters are enough to
identify the desired jail. Alternately, use **ALL** to apply the command
to all created jails.

.. tip:: Partial UUIDs can also be supplied for any other iocage
   operation or subcommand.

.. index:: Jail Start
.. _Startjail:

Start
+++++

To start a jail with the custom tag **www01**, type:

:samp:`# iocage start www01`

A jail can also be started with a full UUID:

:samp:`# iocage start 26e8e027-f00c-11e4-8f7f-3c970e80eb61`

A partial UUID is also acceptable:

:samp:`# iocage start 26e8`

.. index:: Jail Stop
.. _Stopjail:

Stop
++++

The syntax for the **stop** subcommand is the same as **start**:

:samp:`# iocage stop www01`

:samp:`# iocage stop 26e8e027-f00c-11e4-8f7f-3c970e80eb61`

:samp:`# iocage stop 26e8`

.. index:: Jail Restart
.. _Restartjail:

Restart
+++++++

The **restart** subcommand also uses the same syntax as **start** and
**stop**:

:samp:`# iocage restart www01`

:samp:`# iocage restart 26e8e027-f00c-11e4-8f7f-3c970e80eb61`

:samp:`# iocage restart 26e8`

.. index:: Configure a Jail
.. _Configure a Jail:

Configure a Jail
----------------

Configuring the properties of an already created jail is best done with
the **set** and **get** subcommands. Be sure to provide the tag or UUID
of the desired jail when using these subcommands.

.. index:: Set Property
.. _Set Jail Property:

Set Jail Property
+++++++++++++++++

:command:`iocage` uses the **set** subcommand to configure jail
properties.

To set the TAG property for a jail (after creation):

:samp:`# iocage set tag=www02 26e8e027`

The full list of jail properties is available in the iocage(8) manual
page PROPERTIES section.

.. index:: Get Property
.. _Get Jail Property:

Get Jail Property
+++++++++++++++++

To view a specific jail property, use the **get** subcommand:

:samp:`# iocage get tag 26e8e027`

Get all properties:
+++++++++++++++++++

Display the full list of a jail's properties:

:samp:`# iocage get all 26e8e027 | more`

.. index:: Destroy a Jail
.. _Destroy a Jail:

Destroy a Jail
--------------

Destroy a specific jail using the **destroy** subcommand:

:samp:`# iocage destroy www02`

.. warning:: This irreversibly destroys the jail!
