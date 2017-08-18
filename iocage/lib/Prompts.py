import iocage.lib.helpers


class Prompts:

    def __init__(self, host=None):
        iocage.lib.helpers.init_host(self, host)

    def release(self):
        i = 0
        default = None
        available_releases = self.host.distribution.releases
        for available_release in available_releases:
            if available_release.name == self.host.release_version:
                default = i
                print(f"[{i}] \033[1m{available_release.name}\033[0m")
            else:
                print(f"[{i}] {available_release.name}")
            i += 1

        default_release = available_releases[default]
        selection = input(f"Release ({default_release.name}) [{default}]: ")

        if selection == "":
            return default_release
        else:
            return available_releases[int(selection)]
