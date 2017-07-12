.. iocage documentation master file, created by
   sphinx-quickstart on Wed Jul  9 10:19:09 2014.
   You can adapt this file completely to your liking, but it should at
   least contain the root `toctree` directive.

===============================
iocage - A FreeBSD Jail Manager
===============================

iocage is a zero dependency drop in jail/container manager, combining
some of the best features and technologies the FreeBSD operating system
has to offer. It is geared for ease of use with a simplistic and easy to
learn command syntax.

**FEATURES:**

- Templates, basejails, and normal jails
- Easy to use
- Rapid thin provisioning within seconds
- Automatic package installation
- Virtual networking stacks (vnet)
- Shared IP based jails (non vnet)
- Dedicated ZFS datasets inside jails
- Transparent ZFS snapshot management
- Binary updates
- Export and import
- And many more!

Documentation:
--------------

.. toctree::
   :maxdepth: 2

   basic-use
   networking
   jailtypes
   best-practices
   advanced-use
   templates
   debian
   known-issues
   faq

.. Missing File: automatic-package-installation

Indices and tables
==================

 * :ref:`genindex`
 * :ref:`modindex`
 * :ref:`search`
