==========
Jail types
==========

iocage supports five different jail types:

* thick (default)
* thin
* base
* template
* empty

All types have their pros & cons and serves different needs.

Full (thick)
------------

Full (thick) jail is the default type and it is created with the following command:

``iocage create``

A full jail has a fully independent ZFS dataset suitable for network replication
(ZFS send/recv).

Clone (thin)
------------

Thin jails are lightweight clones created with:

``iocage create -c``

Thin jails are cloned from the appropriate RELEASE at creation time and consume
only a fraction of space, preserving only the changing data.

Base
----

The original basejail concept based on nullfs mounts got popularized by ezjail.
iocage basejails use independent read-only ZFS filesystem clones to achieve the
same functionality.

To create a basejail execute:

``iocage create -b``

Basejails re-clone their base filesystems at each startup. They are ideal for
environments where patching or upgrades are required at once to multiple jails.

Template
--------

Template is just another jail where the "template" property is set to "yes".

To turn a jail into a template simply execute:

``iocate set template=yes UUID|TAG``

After this operation the jail can be listed with:

``iocage list -t``

To deploy a jail from this template, execute:

``iocage clone TEMPLATE_UUID tag=mynewjail``

Templates can be converted back and forth with setting the "template" property.

Empty
-----

Empty jails are intended for unsupported jail setups or testing.
To create an empty jail run:

``iocage create -e``

These are ideal for experimentation with unsupported RELEASES or Linux jails.
