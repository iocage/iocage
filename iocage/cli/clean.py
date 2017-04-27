"""clean module for the cli."""
import click

from iocage.lib.ioc_clean import IOCClean
from iocage.lib.ioc_common import logit

__cmdname__ = "clean_cmd"
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
def clean_cmd(force, dataset_type):
    """Calls the correct destroy function."""
    if dataset_type == "jails":
        if not force:
            logit({
                "level"  : "WARNING",
                "message": "\nThis will destroy ALL jails and any "
                           "snapshots on a RELEASE,"
                           "including templates!"
            })
            if not click.confirm("\nAre you sure?"):
                exit()

        IOCClean().clean_jails()
        logit({
            "level"  : "INFO",
            "message": "All iocage jail datasets have been destroyed."
        })
    elif dataset_type == "all":
        if not force:
            logit({
                "level"  : "WARNING",
                "message": "\nThis will destroy ALL iocage data!"
            })
            if not click.confirm("\nAre you sure?"):
                exit()

        IOCClean().clean_all()
        logit({
            "level"  : "INFO",
            "message": "All iocage datasets have been destroyed."
        })
    elif dataset_type == "release":
        pass
    elif dataset_type == "template":
        if not force:
            logit({
                "level"  : "WARNING",
                "message": "This will destroy ALL templates and jails"
                           " created from them!"
            })
            if not click.confirm("\nAre you sure?"):
                exit()

        IOCClean().clean_templates()
        logit({
            "level"  : "INFO",
            "message": "All iocage template datasets have been destroyed."
        })
    else:
        logit({
            "level"  : "ERROR",
            "message": "Please specify a dataset type to clean!"
        })
        exit(1)
