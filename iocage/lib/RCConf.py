import helpers


class RCConf:

    def __init__(self, jail, logger=None):
        helpers.init_logger(self, logger)
        self.jail = jail
        self.content = ""

    def enable_service(self, name):
        self.set_service(name, enabled=True)

    def disable_service(self, name):
        self.set_service(name, enabled=False)

    def set_service(self, name, enabled):

    def read_file(self, file=None):
        if file is None:
            file = f"{self.jail.path}/root"

        self.logger.spam(f"Reading rc.conf from {file}")
        with open(file, "r") as f:
            content = f.read().decode("UTF-8")
            self.content = list(map(
                lambda x: x.strip(),
                content.split("\n")
            ))
