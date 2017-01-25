Create a Debian Squeeze jail (GNU/kFreeBSD)
===========================================

**In this howto we will set up a Debian (GNU/kFreeBSD) jail. GNrUkFreeBSD is a
Debian userland tailored for the FreeBSD kernel.**

Don't forget to replace UUID with your jail's full UUID!

**Create an empty jail with linux specifics:**

``iocage create -e tag=debian exec_start="/etc/init.d/rc 3"
exec_stop="/etc/init.d/rc 0"``

**Install debootstrap on the host:**

``pkg install debootstrap``

**Grab the mountpoint for our empty jail, append /root/ to it and run
debootstrap:**

``iocage get mountpoint UUID | TAG``

``debootstrap squeeze /iocage/jails/UUID/root/`` (you can replace squeeze with wheezy if that is what you need)

**Edit the jail's fstab and add these lines:**

``/iocage/jails/UUID/fstab``

     ::

        linsys   /iocage/jails/UUID/root/sys         linsysfs  rw          0 0
        linproc  /iocage/jails/UUID/root/proc        linprocfs rw          0 0
        tmpfs    /iocage/jails/UUID/root/lib/init/rw tmpfs     rw,mode=777 0 0

**Start the jail and attach to it:**

``iocage start UUID | TAG``

``iocage console UUID | TAG``

What you gain is a 64bit Debian Linux userland. Please note this is not
recommended for production use. The intention was to show that iocage will let
you do almost anything you want with your jails.

If you wish to install a Linux only Debian jail you can follow this tutorial:
`debian-linux-freebsd-jail-zfs
<http://devil-detail.blogspot.co.nz/2013/08/debian-linux-freebsd-jail-zfs.html>`_

