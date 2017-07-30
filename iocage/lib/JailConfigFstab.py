import helpers


class JailConfigFstab:

    def __init__(self, jail, logger=None):
        helpers.init_logger(self, logger)
        self.jail = jail

    @property
    def path(self):
        return f"{self.jail.path}/fstab"

    def write(self):
        with open(self.path, "w") as f:
            f.write(self.__str__())
            self.logger.verbose(f"{self.path} written")

    def __str__(self):

        basejail = self.jail.config.basejail
        basejail_type = self.jail.config.basejail_type
        if not basejail or not basejail_type == "nullfs":
            return ""

        fstab_lines = []
        for basedir in helpers.get_basedir_list():
            release_directory = self.jail.host.datasets.releases.mountpoint

            cloned_release = self.jail.config.cloned_release
            source = f"{release_directory}/{cloned_release}/root/{basedir}"
            destination = f"{self.jail.path}/root/{basedir}"
            fstab_lines.append("\t".join([
                source,
                destination,
                "nullfs",
                "ro",
                "0",
                "0"
            ]))

        return "\n".join(fstab_lines)
