"""fstab module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="fstab", help="Manipulate the specified jails fstab.")
@click.argument("jail")
@click.argument("fstab_string", nargs=-1)
@click.option("--add", "-a", "action",
              help="Adds an entry to the jails fstab and mounts it.",
              flag_value="add")
@click.option("--remove", "-r", "action",
              help="Removes an entry from the jails fstab and unmounts it.",
              flag_value="remove")
@click.option("--edit", "-e", "action",
              help="Opens up the fstab file in your environments EDITOR.",
              flag_value="edit")
def cli(action, fstab_string, jail):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to manipulate the fstab.
    """
    index = None
    _index = False
    add_path = False
    fstab_string = list(fstab_string)

    if not fstab_string and action != "edit":
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please supply a fstab entry or jail!"
        })

    # The user will expect to supply a string, the API would prefer these
    # separate. If the user supplies a quoted string, we will split it,
    # otherwise the format is acceptable to be imported directly.
    if len(fstab_string) == 1:
        try:
            source, destination, fstype, options, dump, _pass = fstab_string[
                0].split()
        except ValueError:
            # We're going to assume this is an index number.
            try:
                index = int(fstab_string[0])

                _index = True
                source, destination, fstype, options, dump, _pass = "", "", \
                                                                    "", "", \
                                                                    "", ""
            except TypeError:
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": "Please specify either a valid fstab "
                               "entry or an index number."
                })
                exit(1)
            except ValueError:
                # We will assume this is just a source, and will do a readonly
                # nullfs mount
                source = fstab_string[0]
                destination = source
                fstype = "nullfs"
                options = "ro"
                dump = "0"
                _pass = "0"
    else:
        if action != "edit":
            try:
                source, destination, fstype, options, dump, _pass = \
                    fstab_string
            except ValueError:
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": "Please specify a valid fstab entry!\n\n"
                               "Example:\n  /the/source /dest FSTYPE "
                               "FSOPTIONS FSDUMP FSPASS"
                })
                exit(1)
        else:
            source, destination, fstype, options, dump, _pass = "", "", \
                                                                "", "", \
                                                                "", ""

    if not _index:
        add_path = True

    ioc.IOCage(jail).fstab(action, source, destination, fstype, options,
                           dump, _pass, index=index, add_path=add_path)
