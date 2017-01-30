iocage
======

**A FreeBSD jail manager.**

iocage is a jail/container manager amalgamating some of the best features and
technologies the FreeBSD operating system has to offer. It is geared for ease
 of use with a simple and easy to understand command syntax.

iocage is in the FreeBSD ports tree as sysutils/py-iocage.
To install using binary packages, simply run: `pkg install py27-iocage`

If cloning the repo directly:
- cd into the cloned directory and run `pip 
install .` as root.
- copy `rc.d/iocage` to `/usr/local/etc/rc.d/iocage`

To install subsequent updates: `git pull` and `pip install -U .`



## WARNING:
- This is beta quality software, there be dragons! Please report them.
- Some features of the previous iocage_legacy are either being dropped or simply not ported yet, feel free to open an issue asking about your favorite feature. But please search before opening a new one. PR's welcome for any feature you want!
- **[DOCUMENTATION (Old documentation, some still applies)](http://iocage.readthedocs.org/en/latest/index.html)**
- **Mailing list**: https://groups.google.com/forum/#!forum/iocage

####Raising an issue:

We _like_ issues! If you are having trouble with `iocage` please open a GitHub [issue](https://github.com/iocage/iocage/issues) and we will ~~run around with our hair on fire~~ look into it. Before doing so, please give us some information about the situation:
- Tell us what version of FreeBSD you are using with something like `uname -ro`
- It would also be helpful if you gave us the output of `iocage --version`
- Most importantly, try to be detailed. Simply stating "I tried consoling into a jail and it broke" will not help us very much.
- Use the [Markdown Basics](https://help.github.com/articles/markdown-basics/#code-formatting) GitHub page for more information on how to paste lines of code and terminal output.

####Submitting a pull request:
Please be detailed on the exact use case of your change and a short demo of
it. Make sure it conforms with PEP-8 and that you supply a test with it if
relevant. Lines may not be longer then 80 characters.

**FEATURES:**
- Ease of use
- Rapid jail creation within seconds
- Automatic package installation
- Virtual networking stacks (vnet)
- Shared IP based jails (non vnet)
- Transparent ZFS snapshot management
- Export and import
- And many more!

---
**QUICK HOWTO:**

Activate a zpool:

`iocage activate ZPOOL`

*NOTE: ZPOOL is a placeholder. Use `zpool list` and substitue it for the 
zpool you wish to use.*

Fetch a release:

`iocage fetch`

Create a jail:

`iocage create tag=myjail ip4_addr="em0|192.168.1.10/24" -r 11.0-RELEASE`

*NOTE: em0 and 11.0-RELEASE are placeholders. Please replace them with your 
real interface (`ifconfig`) and RELEASE chosen during `iocage fetch`.*

Start the jail:

`iocage start myjail`



Congratulations, you have created your first jail with iocage!
You can now use it like you would a real system.
Since SSH won't be available by default, `iocage console myjail` is a useful 
spot to begin configuration of your jail.

To see a list of commands available to you now, type `iocage` outside the jail.

------

**REQUIREMENTS**
- FreeBSD 9.3-RELEASE amd64 and higher or HardenedBSD/TrueOS
- ZFS file system
- Python 2.7

**Optional**
 - Kernel compiled with:

        # This is optional and only needed if you need VNET

        options         VIMAGE # VNET/Vimage support

**Helpful Considerations**
- For the explanations on jail properties read jail(8)
- Create bridge0 and bridge1 interfaces for VNET jails to attach to.
- Use `iocage set` to modify properties and `iocage get` to retrieve property
 values
- Type `iocage COMMAND --help` to see any flags the command supports and
their help. *Example: `iocage create --help`*
- If using VNET consider adding the following to `/etc/sysctl.conf` on the host:

        net.inet.ip.forwarding=1       # Enable IP forwarding between interfaces
        net.link.bridge.pfil_onlyip=0  # Only pass IP packets when pfil is enabled
        net.link.bridge.pfil_bridge=0  # Packet filter on the bridge interface
        net.link.bridge.pfil_member=0  # Packet filter on the member interface
