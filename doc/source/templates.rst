.. index:: Using Templates
.. _Using Templates:

Using Templates
===============

**Templates can save precious time!**

Set up a jail and create a template from it. All packages and
preconfigured settings remain available for deployment to new jails
within seconds.

Any jail can be converted between jail and template as needed.
Essentially, a template is just another jail which has the property
**template** set to **yes**. The difference is templates are not started
by :command:`iocage`.

**Create a template with iocage:**

1. Create a jail: :samp:`# iocage create -r 11.0-RELEASE -n mytemplate`.
2. Configure the jail's networking.
3. Install packages and/or customize the jail as needed.
4. Once finished with customization, stop the jail:
   :samp:`# iocage stop mytemplate`.
5. It is recommended to add notes to the jail, so the specific jail
   customizations are easily remembered:
   :samp:`# iocage set notes="customized PHP,nginx jail" mytemplate`
6. Set the **template** property **on**:
   :samp:`# iocage set template=yes mytemplate`.
7. Find the new template with :command:`iocage list -t`.

**Use the created template:**

Use :command:`iocage create -t` to create a new jail from the new
template:

1. :samp:`# iocage create -t mytemplate -n jailfromtemplate`
2. Find the new jail with :command:`iocage list`.
3. Start the jail with :samp:`# iocage start jailfromtemplate`.

Done!

**Customizing a template:**

To make further customizations or just patch the template, there are two
options:

* Convert the template back to a jail with
  :command:`iocage set template=no [UUID | NAME]`, then start the jail
  with :command:`iocage start [UUID | NAME]`.
* If network access is unnecessary to make the changes, use
  :command:`iocage chroot [UUID | NAME] [Command ...]` to run the
  needed commands inside the template.
