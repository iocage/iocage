.. iocage documentation master file, created by
   sphinx-quickstart on Wed Jul  9 10:19:09 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

===============================
iocage - A FreeBSD jail manager
===============================

iocage is a zero dependency drop in jail/container manager amalgamating some
of the best features and technologies FreeBSD operating system has to offer.
It is geared for ease of use with a simple and easy to understand command
syntax.

**FEATURES:**

- Templates, clones, basejails, fully independent jails
- Ease of use
- Zero configuration files
- Rapid thin provisioning within seconds
- Automatic package installation
- Virtual networking stacks (vnet)
- Shared IP based jails (non vnet)
- Resource limits (CPU, MEMORY, etc.)
- Filesystem quotas and reservations
- Dedicated ZFS datasets inside jails
- Transparent ZFS snapshot management
- Binary updates
- Differential jail packaging
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
   automatic-package-installation
   jail-package
   debian
   known-issues
   faq

Indices and tables
==================

 * :ref:`genindex`
 * :ref:`modindex`
 * :ref:`search`

