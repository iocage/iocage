"""iocage export and import module"""
import fnmatch
import os
import zipfile
from datetime import datetime
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_call

from iocage.lib.ioc_common import checkoutput, logit
from iocage.lib.ioc_json import IOCJson


class IOCImage(object):
    """export() and import()"""

    def __init__(self, callback=None, silent=False):
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.date = datetime.utcnow().strftime("%F")
        self.callback = callback
        self.silent = silent

    def export_jail(self, uuid, tag, path):
        """Make a recursive snapshot of the jail and export to a file."""
        images = f"{self.iocroot}/images"
        name = f"{uuid}_{self.date}"
        image = f"{images}/{name}_{tag}"
        image_path = f"{self.pool}{path}"
        jail_list = []

        # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
        target = f"{image_path}@ioc-export-{self.date}"

        try:
            checkoutput(["zfs", "snapshot", "-r", target], stderr=STDOUT)
        except CalledProcessError as err:
            raise RuntimeError(f"{err.output.decode('utf-8').rstrip()}")

        datasets = Popen(["zfs", "list", "-H", "-r",
                          "-o", "name", f"{self.pool}{path}"],
                         stdout=PIPE, stderr=PIPE).communicate()[0].decode(
            "utf-8").split()

        for dataset in datasets:
            if len(dataset) == 54:
                _image = image
                jail_list.append(_image)
            elif len(dataset) > 54:
                image_name = dataset.partition(f"{self.pool}{path}")[2]
                name = image_name.replace("/", "_")
                _image = image + name
                jail_list.append(_image)
                target = f"{dataset}@ioc-export-{self.date}"

            # Sending each individually as sending them recursively to a file
            # does not work how one expects.
            try:
                with open(_image, "wb") as export:
                    msg = f"Exporting dataset: {dataset}"
                    logit({"level": "INFO", "message": msg}, self.callback,
                          silent=self.silent)

                    check_call(["zfs", "send", target], stdout=export)
            except CalledProcessError as err:
                raise RuntimeError(err)

        msg = f"\nPreparing zip file: {image}.zip."
        logit({"level": "INFO", "message": msg}, self.callback,
              silent=self.silent)

        with zipfile.ZipFile(f"{image}.zip", "w",
                             compression=zipfile.ZIP_DEFLATED,
                             allowZip64=True) as final:
            os.chdir(images)

            for jail in jail_list:
                final.write(jail)

        # Cleanup our mess.
        try:
            checkoutput(["zfs", "destroy", "-r", target], stderr=STDOUT)

            for jail in jail_list:
                os.remove(jail)

        except CalledProcessError as err:
            raise RuntimeError(f"{err.output.decode('utf-8').rstrip()}")

        msg = f"\nExported: {image}.zip"
        logit({"level": "INFO", "message": msg}, self.callback,
              silent=self.silent)

    def import_jail(self, jail):
        """Import from an iocage export."""
        image_dir = f"{self.iocroot}/images"
        exports = os.listdir(image_dir)
        uuid_matches = fnmatch.filter(exports, f"{jail}*.zip")
        tag_matches = fnmatch.filter(exports, f"*{jail}.zip")
        cmd = ["zfs", "recv", "-F", "-d", self.pool]

        # We want to allow the user some flexibility.
        if uuid_matches:
            matches = uuid_matches
        else:
            matches = tag_matches

        if len(matches) == 1:
            image_target = f"{image_dir}/{matches[0]}"
            uuid = matches[0].rsplit("_")[0]
            date = matches[0].rsplit("_")[1]
            tag = matches[0].rsplit("_")[2].rsplit(".")[0]
        elif len(matches) > 1:
            msg = f"Multiple exports found for {jail}:"

            for j in sorted(matches):
                msg += f"\n  {j}"

            raise RuntimeError(msg)
        else:
            raise RuntimeError(f"{jail} not found!")

        with zipfile.ZipFile(image_target, "r") as _import:
            for z in _import.namelist():
                z_split = z.split("_")

                # We don't want the date and tag
                del z_split[1]
                del z_split[1]

                z_split_str = "/".join(z_split)
                _z = z_split_str.replace("iocage/images/", "")

                msg = f"Importing dataset: {_z}"
                logit({"level": "INFO", "message": msg}, self.callback,
                      silent=self.silent)

                dataset = _import.read(z)
                recv = Popen(cmd, stdin=PIPE)
                recv.stdin.write(dataset)
                recv.communicate()
                recv.stdin.close()

        # Cleanup our mess.
        try:
            target = f"{self.pool}{self.iocroot}/jails/{uuid}@ioc-export-" \
                     f"{date}"

            checkoutput(["zfs", "destroy", "-r", target], stderr=STDOUT)
        except CalledProcessError as err:
            raise RuntimeError(f"{err.output.decode('utf-8').rstrip()}")

        tag = IOCJson(f"{self.iocroot}/jails/{uuid}",
                      silent=True).json_set_value(f"tag={tag}")

        msg = f"\nImported: {uuid} ({tag})"
        logit({"level": "INFO", "message": msg}, self.callback,
              silent=self.silent)
