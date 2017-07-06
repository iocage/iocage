.. index:: Jail Types
.. _Jail Types:

Jail Types
==========

iocage supports five different jail types:

* Full (default)
* Clone (lightweight)
* Basejail
* Template
* Empty

All jail types have specific benefits and drawbacks, serving a variety
of unique needs. This section describes and has creation examples for
each of these jail types.

.. index:: Full Jails
.. _Full:

Full
----

The default **full** type jail is created with this command:

:samp:`# iocage create -r 11.0-RELEASE`

A **full** jail contains a fully independent ZFS dataset suitable for
network replication (ZFS send/recv).

.. index:: Clone Jails
.. _Clone:

Clone (lightweight)
-------------------

Clone jails are created with:

:samp:`# iocage create -r 11.0-RELEASE -c 2`

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
:command:`iocage` use independent read-only ZFS filesystem clones to
achieve the same functionality.

Create a basejail by typing:

:command:`iocage create -r [RELEASE] -b`

Basejails re-clone their base filesystems at each startup. They are
ideal for environments where immediate patching or upgrading of multiple
jails is requires.

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

:samp:`# iocage create -t examplejail tag=newexampjail`

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
