.. index:: Plugins
.. _Plugins:

Plugins
=======

iocage plugins are a simple and very fast method to get application
containers installed and configured. At its core, a plugin is a jail
specifically running one program. Popular programs can be installed
repeatedly with one line. Additionally, plugins are easily extended by
users, offering a high level of customizability and functionality.

In structure, a plugin consists of :file:`.json` manifest and
:file:`.png` icon files.


**See what's available**


To see a list of all currently available plugins, open a command line
and type :command:`iocage list -PR` or
:command:`iocage list --plugins --remote`. The full
`iocage plugin list <https://raw.githubusercontent.com/freenas/iocage-ix-plugins/master/INDEX>`_
is also available on GitHub.

Check which plugins are installed on the system with
:command:`iocage list --plugins` or :command:`iocage list -P`.


**Getting started with plugins**


.. note:: iocage needs to be `activated <Activate iocage>`_ before
   plugins can be installed or modified!


To get started, open a command line and type
:command:`iocage fetch --plugins ip4_addr="IF|IP"`. This initial
:command:`fetch` also supports *dhcp* in the same manner as
:command:`iocage create`. The IP listed for the plugin needs to
be a valid IP not already in use. Use the *- -name* flag to easily fetch a
specific plugin:

:samp:`$ iocage fetch --plugins --name plexmediaserver ip4_addr="igb0|192.168.0.91"`

If available, plugins can also be fetched locally with
:command:`iocage fetch -P the/path/to/plugin.json ip4_addr="re0|192.168.0.100"`


.. tip:: Using :command:`iocage fetch` locally is very useful when
   testing an in-development plugin.


After fetching a plugin, view of all its properties with
:command:`iocage get -a NAME|UUID | less`. Individual properties are
found with :command:`iocage get PROPERTY`:

:samp:`$ iocage get type quasselcore`

Adjust the plugin properties with :command:`iocage set`:

:samp:`$ iocage set PROPERTY quasselcore`


:command:`iocage set` is used to configure
that plugin. In this example, a complete Quasselcore plugin is
installed to a FreeNAS system, then the note of the plugin is changed:

.. code-block:: none

    [root@freenas ~]# iocage fetch --plugins --name quasselcore ip4_addr="em0|192.168.1.50"
    [root@freenas ~]# iocage set notes="Hello world" quasselcore
    [root@freenas ~]# iocage get notes quasselcore
    Hello world


**Upgrading and updating plugins**


The process for upgrading and updating plugins is exactly the same as
normal jails. See :ref:`Updating Jails` or :ref:`Upgrading Jails` .
