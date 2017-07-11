.. index:: Best Practices
.. _Best Practices:

Best Practices
--------------

This section provides some generic guidelines and tips for working with
:command:`iocage` managed jails.

**Use PF as a module**

  This is the default setting in the *GENERIC* kernel. There seems to be
  a VNET bug which is only triggered when PF is directly compiled into
  the kernel.

**Always name jails and templates!**

  Use the -n option with :command:`iocage create` to set a name for the
  jail. This helps avoid mistakes and easily identify jails.

  Example: :samp:`iocage create -r 11.0-RELEASE -n testjail`

**Set the notes property**

  Set the **notes** property to something meaningful, especially for
  templates and jails used infrequently.

  Example:

  .. code-block:: none

   [root@tester ~]# iocage set notes="This is a test jail." testjail
   Property: notes has been updated to This is a test jail.

   [root@tester ~]# iocage get notes testjail
   This is a test jail.

**VNET**

  *VNET* provides more fine control and isolation for jails. VNET also
  allows jails to run their own firewalls. See :ref:`Known Issues` for
  more about VNET.

**Discover templates!**

  Templates simplify using jail creation and customization, give it a
  try! See :ref:`Using Templates` to get started.

**Use** :command:`iocage restart` **instead of start/stop**

  Always restart a jail with the :command:`iocage restart -s` command.
  This performs a soft restart and leaves the *VNET* stack alone, which
  is less stressful for both kernel and user.

**Check the firewall rules**

  When using *IPFW* inside a *VNET* jail, put **firewall_enable="YES"**
  and **firewall_type="open"** into :file:`/etc/rc.conf`. This excludes
  the firewall from accidentally blocking the user right from the
  beginning! Re-lock it once finished testing. It is also recommended to
  check the *PF* firewall rules on the host if jail and host rules are
  mixed.

**Delete old snapshots**

  Remove unnecessary snapshots, especially from jails where data is
  constantly changing!

**Use** :command:`iocage chroot`

  When accessing or modifying files in a template or stopped jail, use
  :command:`iocage chroot [UUID | NAME] [Command ...]`. This
  way you don't need to spin up the jail or convert the template.
  
