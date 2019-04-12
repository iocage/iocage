.. index:: Jail Types
.. _Jail Types:

Jail Types
==========

iocage supports several different jail types:

* Clone (default)
* Basejail
* Template
* Empty
* Thickjail

All jail types have specific benefits and drawbacks, serving a variety
of unique needs. This section describes and has creation examples for
each of these jail types.

.. index:: Clone Jails
.. _Clone:

Clone (default)
---------------

Clone jails are created with:

:samp:`# iocage create -r 11.0-RELEASE`

Clone jails are duplicated from the appropriate RELEASE at creation
time. These consume a small amount of space, preserving only the
changing data.

.. index:: Basejails
.. _Basejail:

Basejail
--------

The original basejail concept was based on nullfs mounts. It was
popularized by `ezjail <http://erdgeist.org/arts/software/ezjail/>`_,
but :command:`iocage` basejails are a little different. Basejails in
:command:`iocage` are mounts in a jail **fstab** that are mounted at
jail startup.

Create a basejail by typing:

:command:`iocage create -r [RELEASE] -b`

Basejails mount their **fstab** mounts at each startup. They are ideal
for environments where immediate patching or upgrading of multiple
jails is required.

.. index:: Template Jails
.. _Template:

Template
--------

Template jails are customized jails used to quickly create further
custom jails.

For example, after creating a jail, the user customizes
that jail's networking properties. Once satisfied, the user then changes
the jail into a template with:

:samp:`# iocage set template=yes examplejail`

After this operation the jail is found in the *templates* list:

:samp:`# iocage list -t`

And new jails with the user customized networking can be created:

:samp:`# iocage create -t examplejail -n newexamplejail`

Template jails are convertable by setting the *template=*
property.

.. index:: Empty Jails
.. _Empty:

Empty
-----

Empty jails are intended for unsupported jail setups or testing. Create
an empty jail with :command:`iocage create -e`.

These are ideal for experimentation with unsupported RELEASES or Linux
jails.

.. index:: Thickjail
.. _Thick:

Thickjail
---------

Thickjails jails are created with:

:samp:`# iocage create -T -r 11.2-RELEASE`

Thickjails are copied from the appropriate RELEASE at creation
time. These consume a large amount of space, but are fully independent.

These are ideal for transmission or synchronization between different 
hosts with :command:`zfs send` and :command:`zfs receive`.
