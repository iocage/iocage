import helpers


class Prompts:

    def __init__(self, host=None):
        helpers.init_host(self, host)

    def release(self):
        i = 0
        default = None
        for available_release in self.host.distribution.releases:
            if available_release.name == self.host.release_version:
                default = i
                print(f"[{i}] \033[1m{available_release.name}\033[0m")
            else:
                print(f"[{i}] {available_release.name}")
            i += 1
        return default
