===========
Basic usage
===========

This section is about basic use and is a suitable quick howto for newcomers.

Fetch a release
---------------

The very first step with iocage is to fetch a RELEASE. By default iocage will attempt to fetch the
host's current RELEASE from the freebsd.org servers. Once the RELEASE bits are downloaded, the most
recent patches are applied too.

Simply run:

``iocage fetch``

If a specific RELEASE is required run:

``iocage fetch release=9.3-RELEASE``

In case a specific download mirror is required simply run:

``iocage fetch ftphost=ftp.hostname.org``

You can also specify a ftp directory to fetch the base files from:

``iocage fetch ftpdir=/dir/``

Create a jail
-------------

There are three supported basic jail types: full, clone and base jail. In addition to these three 
there are two more which are discussed later (empty and templates).
Depending on requirements the `create` subcommand can be tweaked to create any of the three types.
By default iocage will create a fully independent jail of the current host's RELEASE and set the TAG property to todays date.

Creating a jail is real simple, just run:

``iocage create``

This will create a fully independent jail.

To create a lightweight jail (clone) run:

``iocage create -c``

To create a base jail:

``iocage create -b``

To create a jail and set its IP address and tag property run:

``iocage create -c tag=myjail ip4_addr="em0|10.1.1.10/24"``

For more information please read iocage(8).

Listing jails
-------------

To list all jails run:

``iocage list``

To see all downloaded RELEASEs run:

``iocage list -r``

To see available templates run:

``iocage list -t``

Start, stop or restart a jail
-----------------------------

To start or stop any jail on the system both the UUID or TAG can be used interchangeably.
To simplify UUID handling iocage accepts a partial UUID too with any subcommand.

Start
+++++

To start a jail tagged www01 simply run:

``iocage start www01``

To start a jail with a full UUID run:

``iocage start 26e8e027-f00c-11e4-8f7f-3c970e80eb61``

Or to start the jail only with a partial UUID enter the first few characters only:

``iocage start 26e8``

Stop
++++

To stop a jail just use the ``stop`` subcommand instead of start:

``iocage stop www01``

Restart
+++++++

To restart a jail run:

``iocage restart www01``

*Note: Short UUIDs are supported with all operations and subcommands within iocage.*

Configure a jail
----------------

Any property can be reconfigured with the ``set`` subcommand.

Set property
++++++++++++

To set the jail's TAG property run:

``iocage set tag=www02 26e8e027``

Get property
++++++++++++

To verify any property simply run the ``get`` subcommand:

``iocage get tag 26e8e027``

Get all properties:
+++++++++++++++++++

Or to display all supported properties run:

``iocage get all 26e8e027``

System wide defaults
--------------------

Starting with version 1.6.0 system wide defaults can be set. These defaults will be re-applied for all
newly created jails. To create a system wide default override for a property simply specify the ``default`` keyword instead of a jail UUID or TAG.

Example, to turn off VNET capability for all newly created jails run:

``iocage set vnet=off default``

Destroy a jails
---------------

To destroy a jail, simply run:

``iocage destroy www02``

**Warning:** this will irreversibly destroy the jail!
