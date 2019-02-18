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

To make changes to the template, you will need to know whether any existing
jails are based on the template. Since modifying the template will require
converting it back into a jail, it cannot be the base for any jails.

*** No jails based on the template ***

1. Convert the template back into a jail:

   :command:`iocage set template=no [UUID | NAME]`.

2. Start the jail:

   :command:`iocage start [UUID | NAME]`.

3. Use any method you wish to connect to the jail and modify its contents.

4. Stop the jail:

   :command:`iocage stop [UUID | NAME]`.

5. Convert the jail back into a template:

   :command:`iocage set template=yes [UUID | NAME]`.

*** Jails based on the template ***

This process will create a new template, leaving the existing template
and jails unaffected.

1. Create a 'thick' jail from the template, so that it will be independent
   from the template:

   :command:`iocage create -T -t [UUID | NAME] -n newtemplate`.

2. Start the jail:

   :command:`iocage start newtemplate`.

3. Use any method you wish to connect to the jail and modify its contents.

4. Stop the jail:

   :command:`iocage stop newtemplate`.

5. Convert the jail into a template:

   :command:`iocage set template=yes newtemplate`.
