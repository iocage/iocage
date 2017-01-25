Best practices
--------------

These are some generic guidelines for working with iocage managed jails.

**Use PF as a module**

  This is the default setting in the ``GENERIC`` kernel. There seems to be a VNET bug which is only
  triggered when PF is directly compiled into the kernel.

**Always tag your jails and templates!**

  This will help you avoid mistakes and easily identify jails.

**Set the notes property**

  Set the ``notes`` property to something meaningful, especially for templates
  and jails you might use only once in a while.

**VNET**

  ``VNET`` will give you more control and isolation. Also allows to run per jail firewalls.
  See known issues about VNET.

**Don't overuse resource limiting!**

  Unless really needed, let the OS decide how to do it best. Set limits with
  the "log action" before enforcing "deny". This way you can check the logs
  before creating any performance bottlenecks.

**Discover templates!**

  Templates will make your life easy, try them!

**Use the restart command instead of start/stop**

  If you wish to restart a jail use the ``restart`` command which performs a
  soft restart and it leaves the ``VNET`` stack alone, less stressful for the
  kernel and you.

**Check your firewall rules**

  When using ``IPFW`` inside a ``VNET`` jail put ``firewall_enable="YES"``
  ``firewall_type="open"`` into ``/etc/rc.conf`` for a start. This way you can exclude
  the firewall from blocking you right from the beginning! Lock it down once you've tested
  everything. Also check PF firewall rules on the host if you happen to mix both.

**Get rid of old snapshots**

  Remove snapshots you don't need, especially from jails where data is changing a lot!

**Use the chroot sub-command**
 
  In case you need to access or modify files in a template or a jail which is in a
  stopped state, use ``iocage chroot UUID | TAG``. This way you don't need to spin up the
  jail or convert the template.
