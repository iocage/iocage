"""clean module for the cli."""
import click

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_clean import IOCClean

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
    lgr = ioc_logger.Logger('ioc_cli_clean')
    lgr = lgr.getLogger()

    if dataset_type == "jails":
        if not force:
            lgr.warning("\nThis will destroy ALL jails"
                        " and any snapshots on a RELEASE, including "
                        "templates!")
            if not click.confirm("\nAre you sure?"):
                exit()

        IOCClean().clean_jails()
        lgr.info("All iocage jail datasets have been destroyed.")
    elif dataset_type == "all":
        if not force:
            lgr.warning("\nThis will destroy ALL iocage data!")
            if not click.confirm("\nAre you sure?"):
                exit()

        IOCClean().clean_all()
        lgr.info("All iocage datasets have been destroyed.")
    elif dataset_type == "release":
        pass
    elif dataset_type == "template":
        if not force:
            lgr.warning("This will destroy ALL templates"
                        " and jails created from them!")
            if not click.confirm("\nAre you sure?"):
                exit()

        IOCClean().clean_templates()
        lgr.info("All iocage template datasets have been destroyed.")
        pass
    else:
        lgr.critical("Please specify a dataset type to clean!")
        exit(1)
