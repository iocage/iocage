"""clean module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="clean", help="Destroy specified dataset types.")
@click.option("--force", "-f", default=False, is_flag=True)
@click.option("--all", "-a", "dataset_type", flag_value="all",
              help="Destroy all iocage data that has been created.")
@click.option("--jails", "-j", "dataset_type", flag_value="jails",
              help="Destroy all jails created.")
@click.option("--base", "-r", "-b", "dataset_type", flag_value="release",
              help="Destroy all RELEASEs fetched.")
@click.option("--template", "-t", "dataset_type", flag_value="template",
              help="Destroy all templates.")
def cli(force, dataset_type):
    """Calls the correct destroy function."""
    if dataset_type == "jails":
        msg = {
            "level"  : "WARNING",
            "message": "\nThis will destroy ALL jails and any "
                       "snapshots on a RELEASE,"
                       "including templates!"
        }
    elif dataset_type == "all":
        msg = {
            "level"  : "WARNING",
            "message": "\nThis will destroy ALL iocage data!"
        }
    elif dataset_type == "release":
        msg = {
            "level"  : "WARNING",
            "message": "\nThis will destroy ALL fetched RELEASES and"
                       " jails/templates created from them!"
        }
    elif dataset_type == "template":
        msg = {
            "level"  : "WARNING",
            "message": "This will destroy ALL templates and jails"
                       " created from them!"
        }
    else:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify a dataset type to clean!"
        })

    if not force:
        ioc_common.logit(msg)
        if not click.confirm("\nAre you sure?"):
            exit()

    ioc.IOCage().clean(dataset_type)
