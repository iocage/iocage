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

.. tip:: iocage has an experimental "color" mode enabled by setting the
   environment variable :command:`IOCAGE_COLOR` to **TRUE**.

.. index:: Setting environment variables
.. _Setting environment variables:

Setting Environment Variables
-----------------------------

iocage currently has four environment variables:

.. table:: **iocage Environment Variables**
   :class: longtable

   +------------------+-----------------+----------------------------------------------------+
   | Name             | Accepted Values | Description                                        |
   +------------------+-----------------+----------------------------------------------------+
   | IOCAGE_LOGFILE   | FILE            | File location to have iocage log into.             |
   +------------------+-----------------+----------------------------------------------------+
   | IOCAGE_COLOR     | TRUE|FALSE      | Turns on a colored CLI output.                     |
   +------------------+-----------------+----------------------------------------------------+
   | IOCAGE_FORCE     | TRUE|FALSE      | Required for any automatic migrations              |
   +------------------+-----------------+----------------------------------------------------+
   | IOCAGE_PLUGIN_IP | IP_ADDR         | This environment variable is set in a plugin jail. |
   |                  |                 | Use it to quickly query it with another            |
   |                  |                 | program/script                                     |
   +------------------+-----------------+----------------------------------------------------+

The process for setting these variables depends on the shell being used.
The defualt FreeBSD shell :command:`csh/tcsh` and the :command:`bash/sh`
shell are different from one another and require a slightly different
process for setting environment variables. For example:

In the FreeBSD shell :command:`csh/tcsh` , :samp:`setenv IOCAGE_COLOR TRUE`
sets the environment variable IOCAGE_COLOR to true.

In the :command:`bash/sh` shell, :samp:`export IOCAGE_COLOR=TRUE` sets
the environment variable IOCAGE_COLOR to true.

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

:command:`iocage` now needs to fetch a RELEASE, which is used to create
jails. By default, typing :command:`iocage fetch` opens a menu for the
user to choose which release to download, as seen in this example:

.. code-block:: none

 # iocage fetch
 [0] 9.3-RELEASE (EOL)
 [1] 10.1-RELEASE (EOL)
 [2] 10.2-RELEASE (EOL)
 [3] 10.3-RELEASE
 [4] 11.0-RELEASE

 Type the number of the desired RELEASE
 Press [Enter] to fetch the default selection: (11.0-RELEASE)
 Type EXIT to quit: 4

Once the desired RELEASE is downloaded, the most recent patches are also
applied to it.

:command:`iocage fetch` also has a number of options and properties for
users to fine-tune the functionality of the command.

To fetch the latest RELEASE,

:samp:`iocage fetch -r LATEST`

If a specific RELEASE is required, use the **-r** option:

:command:`iocage fetch -r [11.0-RELEASE]`


If a specific download mirror is required, use the **-s** option:

:command:`iocage fetch -s [ftp.hostname.org]`

:command:`fetch` can also pull from a specific ftp directory, using the
**-d** option:

:command:`iocage fetch -d [dir/]`

.. index:: Basic Jail Creation
.. _Create a Jail:

Create a Jail
-------------

With a release downloaded, iocage is now able to create jails. There are
two types of jails: **normal** and **base**. More details about these
jail types can be found in the :ref:`Jail Types` section of this
documentation.

Depending on the user's requirements, the :command:`create` subcommand
can be adjusted to create either jail type. By default,
:command:`iocage create` creates a **normal** jail, but invoking the
**-b** option changes the creation to the basejail type. iocage is able
to create a jail with the latest release by adding *LATEST* to the
create command.

Here is an example of creating a normal jail from the latest available
release:

:samp:`# iocage create -r LATEST -n [JAIL]`

This creates a normal jail that is a clone of the latest release.

Here is an example of creating a normal jail from the *11.0-RELEASE*:

:samp:`# iocage create -r 11.0-RELEASE`

This normal jail is a clone of the specified RELEASE.

To create multiple jails, use the **-c** option:

:samp:`# iocage create -r 11.0-RELEASE -c 2`

This example shows the numeric value after the **-c** flag is used to
designate the number of jails to create. In the above example, two jails
are created.

A simple basejail is created with the **-b** option:

:command:`iocage create -b -r [RELEASE]`

After designating the type and number of jails to create with the option
flags, specific jail **properties** can also be set. For example:

:samp:`# iocage create -r 11.0-RELEASE --name myjail boot=on`

Creates a FreeBSD 11.0-RELEASE jail with the custom name *myjail* and
sets the jail to start at system boot time.

More information about jail properties is available in the iocage(8)
FreeBSD manual page, accessible on a FreeBSD system by
typing :command:`man iocage`.

.. index:: Listing Jails
.. _Listing Jails:

Listing Jails
-------------

To list all jails, use :command:`iocage list`

To see all downloaded RELEASEs, use :command:`iocage list -r`

View available templates with :command:`iocage list -t`

.. index:: Jail start stop restart
.. _Start Stop Restart Jail:

Start, Stop, or Restart a Jail
------------------------------

Jails can be started, stopped, or restarted at any time. By default, new
jails are in a *down* (stopped) state. To see the status of all jails,
use :command:`iocage list` and read the **STATE** column.

Use each jail's UUID or custom NAME to start, stop, or restart it.
Partial entries are acceptable, as long as the given characters are
enough to identify the desired jail. Alternately, use **ALL** to apply
the command to all created jails.

.. tip:: Partial entries can also be supplied for any other
   :command:`iocage` operation or subcommand.

.. index:: Jail Start
.. _Startjail:

Start
+++++

Use :command:`iocage start` to start jails.

**Examples:**

Start a jail with the custom name **www01**:

:samp:`iocage start www01`.

If no custom NAME or UUID is provided by the user, :command:`iocage`
automatically assigns a complex UUID to a new jail. This UUID is always
usable when doing :command:`iocage` operations like starting a jail:

:samp:`# iocage start 26e8e027-f00c-11e4-8f7f-3c970e80eb61`

Partial entries are also acceptable:

:samp:`# iocaget start www`

:samp:`# iocage start 26e8`

.. index:: Jail Stop
.. _Stopjail:

Stop
++++

:command:`iocage stop` uses the same syntax as :command:`iocage start`.

**Examples:**

:samp:`# iocage stop www01`

:samp:`# iocage stop 26e8e027-f00c-11e4-8f7f-3c970e80eb61`

:samp:`# iocage stop 26e8`

.. index:: Jail Restart
.. _Restartjail:

Restart
+++++++

:command:`iocage restart` also uses the same syntax as **start** and
**stop**:

:samp:`# iocage restart www01`

:samp:`# iocage restart 26e8e027-f00c-11e4-8f7f-3c970e80eb61`

:samp:`# iocage restart 26e8`

.. index:: Configure a Jail
.. _Configure a Jail:

Configure a Jail
----------------

Configuring the properties of an already created jail is best done with
the **set** and **get** subcommands. Be sure to provide the NAME or UUID
of the desired jail when using these subcommands.

.. index:: Set Property
.. _Set Jail Property:

Set Jail Property
+++++++++++++++++

:command:`iocage` uses the **set** subcommand to configure jail
properties.

To assign a custom note to a jail with the **notes** property:

:samp:`# iocage set notes="This is a test jail." 26e8e027`

The full list of jail properties is available in the iocage(8) manual
page PROPERTIES section.

.. index:: Get Property
.. _Get Jail Property:

Get Jail Property
+++++++++++++++++

To view a specific jail property, use the **get** subcommand:

:samp:`# iocage get notes 26e8e027`

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

.. index:: Rename Jail
.. _Rename Jail:

Rename a Jail
-------------

:command:`iocage` allows jails to be renamed after creation and/or
migration. The :command:`iocage rename` subcommand is used to alter an
existing jail's UUID or NAME. Type the command, then the UUID or name of
the jail to be altered, then the desired name. This example shows using
the :command:`rename` subcommand:

:samp:`# iocage rename jail1 TESTINGJAIL`
