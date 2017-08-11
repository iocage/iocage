import libzfs
import re

import iocage.lib.Jail
import iocage.lib.helpers


class Jails:

    # Keys that are stored on the Jail object, not the configuration
    JAIL_KEYS = [
        "jid",
        "name",
        "running",
        "ip4.addr",
        "ip6.addr"
    ]

    def __init__(self,
                 host=None,
                 logger=None,
                 zfs=None):

        iocage.lib.helpers.init_logger(self, logger)
        iocage.lib.helpers.init_zfs(self, zfs)
        iocage.lib.helpers.init_host(self, host)
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")

    def list(self, filters=None):

        if len(filters) == 1:
            chars = "+*="
            name = filters[0]
            if not any(x in name for x in chars):
                single_jail = iocage.lib.Jail.Jail(
                    {
                        "name": name
                    },
                    logger=self.logger,
                    host=self.host,
                    zfs=self.zfs
                )
                return [single_jail]

        jails = self._get_existing_jails()

        if filters is not None:
            return self._filter_jails(jails, filters)
        else:
            return jails

    def _filter_jails(self, jails, filters):

        filtered_jails = []
        jail_filters = {}

        filter_terms = list(map(_split_filter_map, filters))
        for key, value in filter_terms:
            if key not in jail_filters.keys():
                jail_filters[key] = [value]
            else:
                jail_filters[key].append(value)

        for jail in jails:

            jail_matches = True

            for group in jail_filters.keys():

                # Providing multiple names = OR (e.g. name=foo, name=bar)
                jail_matches_group = False

                for current_filter in jail_filters[group]:
                    if self._jail_matches_filter(jail, group, current_filter):
                        jail_matches_group = True

                if jail_matches_group is False:
                    jail_matches = False
                    continue

            if jail_matches is True:
                filtered_jails.append(jail)

        return filtered_jails

    def _get_existing_jails(self):
        jails_dataset = self.host.datasets.jails
        jail_datasets = list(jails_dataset.children)

        return list(map(
            lambda x: iocage.lib.Jail.Jail({
                "name": x.name.split("/").pop()
            }, logger=self.logger, host=self.host, zfs=self.zfs),
            jail_datasets
        ))

    def _jail_matches_filter(self, jail, key, value):
        for filter_value in self._split_filter_values(value):
            jail_value = self._lookup_jail_value(jail, key)
            if not self._matches_filter(filter_value, jail_value):
                return False
        return True

    def _matches_filter(self, filter_value, value):
        escaped_characters = [".", "$", "^", "(", ")"]
        for character in escaped_characters:
            filter_value = filter_value.replace(character, f"\\{character}")
        filter_value = filter_value.replace("$", "\\$")
        filter_value = filter_value.replace(".", "\\.")
        filter_value = filter_value.replace("*", ".*")
        filter_value = filter_value.replace("+", ".+")
        pattern = f"^{filter_value}$"
        match = re.match(pattern, value)
        return match is not None

    def _lookup_jail_value(self, jail, key):
        if key in Jails.JAIL_KEYS:
            return jail.getattr_str(key)
        else:
            return str(jail.config["__getattr__"](key))

    def _split_filter_values(self, value):
        values = []
        escaped_comma_blocks = map(
            lambda block: block.split(","),
            value.split("\\,")
        )
        for block in escaped_comma_blocks:
            n = len(values)
            if n > 0:
                index = n - 1
                values[index] += f",{block[0]}"
            else:
                values.append(block[0])
            if len(block) > 1:
                values += block[1:]
        return values


def _split_filter_map(x):
    try:
        prop, value = x.split("=", maxsplit=1)
    except:
        prop = "name"
        value = x

    return prop, value
