.. index:: Create a Jail Package
.. _Create a Jail Package:

Create a Jail Package (Legacy ONLY)
===================================

.. warning:: This functionality only exists in legacy versions of
   :command:`iocage`. Basic export/import functionality exists in the
   current version, but full jail packages are not present yet.

**What is a jail package?**

A jail package is a small differential image template. It can be
deployed on top of vanilla jails. The RELEASE and patch level has to
match between the package and a vanilla jail.

:command:`iocage` uses the **record** function for this operation, which
is a **unionfs** mount under the hood.

The resulting package can be stored on a web server with a checksum
file, ready to be deployed anywhere.

Here are the steps to create a jail package:

1. Create a new jail: :samp:`# iocage create -r 11.0-RELEASE tag=nginx`.
2. Start the jail: :samp:`# iocage start nginx`.
3. Configure networking to enable internet access for this jail.
4. Issue :samp:`# iocage record start nginx`. From this point, every
   change is recorded and added to :file:`/iocage/jails/[UUID]/recorded`.
5. In the jail, install *nginx* with
   :samp:`# iocage chroot nginx pkg install nginx`.
6. In the jail, install any other required software.
7. In the jail, customize the configuration files as needed.
8. Once finished with installations and customizations, stop recording
   changes with :command:`iocage record stop [UUID | TAG]`. Another
   option is to stop the jail with :command:`iocage stop [UUID | TAG]`.
9. Examine :file:`/iocage/jails/[UUID]/recorded` and run
   :command:`find /iocage/jails/[UUID]/recorded -type f`.
10. Remove unnecessary files and make any final customizations to the
    jail.
11. Run :command:`iocage package [UUID | TAG]`. This creates a new
    package in :file:`/iocage/packages` with a *SHA256* checksum file.
12. (Optional) Discard the jail with
    :command:`iocage destroy [UUID | TAG]`.

The resulting :file:`[UUID].tar.xz` is deployable on top of any new
jail!

Instructions to deploy a new jail with :file:`[UUID].tar.xz`.

1. Create new jail: :samp:`# iocage create -r 11.0-RELEASE tag=myjail`.
2. Deploy the package: :samp:`# iocage import [UUID] tag=myjail`
3. List jail: :samp:`# iocage list|grep myjail`, note the UUID.
4. Start jail with :command:`iocage start [UUID | TAG]`.
5. Examine the changes and packages - they are all there!

Enjoy!
