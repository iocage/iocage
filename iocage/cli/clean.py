"""clean module for the cli."""
import click

import iocage.lib.ioc_clean as ioc_clean
import iocage.lib.ioc_common as ioc_common

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
        if not force:
            ioc_common.logit({
                "level"  : "WARNING",
                "message": "\nThis will destroy ALL jails and any "
                           "snapshots on a RELEASE,"
                           "including templates!"
            })
            if not click.confirm("\nAre you sure?"):
                exit()

        ioc_clean.IOCClean().clean_jails()
        ioc_common.logit({
            "level"  : "INFO",
            "message": "All iocage jail datasets have been destroyed."
        })
    elif dataset_type == "all":
        if not force:
            ioc_common.logit({
                "level"  : "WARNING",
                "message": "\nThis will destroy ALL iocage data!"
            })
            if not click.confirm("\nAre you sure?"):
                exit()

        ioc_clean.IOCClean().clean_all()
        ioc_common.logit({
            "level"  : "INFO",
            "message": "All iocage datasets have been destroyed."
        })
    elif dataset_type == "release":
        pass
    elif dataset_type == "template":
        if not force:
            ioc_common.logit({
                "level"  : "WARNING",
                "message": "This will destroy ALL templates and jails"
                           " created from them!"
            })
            if not click.confirm("\nAre you sure?"):
                exit()

        ioc_clean.IOCClean().clean_templates()
        ioc_common.logit({
            "level"  : "INFO",
            "message": "All iocage template datasets have been destroyed."
        })
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please specify a dataset type to clean!"
        })
        exit(1)
