import os

import helpers


class FstabLine(dict):

    def __init__(self, data):
        keys = data.keys()
        if "comment" not in keys:
            data["comment"] = None
        dict.__init__(self, data)

    def __str__(self):
        return _line_to_string(self)

    def __hash__(self):
        return hash(self["destination"])


class JailConfigFstab(set):

    AUTO_COMMENT_IDENTIFIER = "iocage-auto"

    def __init__(self, jail, logger=None):
        set.__init__(self)
        helpers.init_logger(self, logger)
        self.jail = jail

    @property
    def fstab_file_path(self):
        return f"{self.jail.path}/fstab"

    def parse_lines(self, input, ignore_auto_created=True):

        set.clear(self)

        for line in input.split("\n"):

            try:
                line, comment = line.split("#", maxsplit=1)
                comment = comment.strip("# ")
                ignored_comment = JailConfigFstab.AUTO_COMMENT_IDENTIFIER
                if ignore_auto_created and (comment == ignored_comment):
                    continue
            except:
                comment = None

            line = line.strip()

            if line == "":
                continue

            fragments = line.split()
            if len(fragments) != 6:
                self.logger.log(
                    f"Invalid line in fstab file {self.fstab_file_path}"
                    " - skipping line"
                )
                continue

            destination = os.path.abspath(fragments[1])

            new_line = FstabLine({
                "source": fragments[0],
                "destination": fragments[1],
                "type": fragments[2],
                "options": fragments[3],
                "dump": fragments[4],
                "passnum": fragments[5],
                "comment": comment
            })

            if new_line in self:
                self.logger.error(
                    "Duplicate mountpoint in fstab: "
                    f"{destination} already mounted"
                )

            self.add_line(new_line)

    def read_file(self):
        if os.path.isfile(self.fstab_file_path):
            with open(self.fstab_file_path, "r") as f:
                self.parse_lines(f.read())
                f.close()

    def save(self):
        self.logger.verbose(f"Writing fstab to {self.fstab_file_path}")
        with open(self.fstab_file_path, "w") as f:
            f.write(self.__str__())
            f.truncate()
            f.close()

        self.logger.verbose(f"{self.jail.path}/fstab written")

    def save_with_basedirs(self):
        return self.save()

    def add(self,
            source,
            destination,
            type="nullfs",
            options="ro",
            dump="0",
            passnum="0",
            comment=None):

        line = FstabLine({
            "source": source,
            "destination": destination,
            "type": type,
            "options": options,
            "dump": dump,
            "passnum": passnum,
            "comment": comment
        })

        return self.add_line(line)

    def add_line(self, line):

        self.logger.debug(f"Adding line to fstab: {line}")
        set.add(self, line)

    @property
    def basejail_lines(self):
        basejail = self.jail.config.basejail
        basejail_type = self.jail.config.basejail_type

        if not (basejail and basejail_type == "nullfs"):
            return []

        fstab_basejail_lines = []
        for basedir in helpers.get_basedir_list():
            release_directory = self.jail.host.datasets.releases.mountpoint

            cloned_release = self.jail.config.cloned_release
            source = f"{release_directory}/{cloned_release}/root/{basedir}"
            destination = f"{self.jail.path}/root/{basedir}"
            fstab_basejail_lines.append({
                "source": source,
                "destination": destination,
                "type": "nullfs",
                "options": "ro",
                "dump": "0",
                "passnum": "0",
                "comment": "iocage-auto"
            })

        return fstab_basejail_lines

    def __str__(self):
        return "\n".join(map(
            _line_to_string,
            list(self)
        )) + "\n"

    def __iter__(self):
        fstab_lines = list(set.__iter__(self))
        fstab_lines += self.basejail_lines
        return iter(fstab_lines)

    def __contains__(self, value):
        for entry in self:
            if value["destination"] == entry["destination"]:
                return True
            else:
                return False


def _line_to_string(line):
    output = "\t".join([
        line["source"],
        line["destination"],
        line["type"],
        line["options"],
        line["dump"],
        line["passnum"]
    ])

    if line["comment"] is not None:
        comment = line["comment"]
        output += f" # {comment}"

    return output
