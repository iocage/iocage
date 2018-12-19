import itertools
import os
import json
import subprocess
import uuid

from datetime import datetime

import libzfs


# A helper class to parse the output of iocage for us to test

class Row:
    powers = {
        'B': 0,
        'K': 3,
        'M': 6,
        'G': 9,
        'T': 12,
        'P': 15
    }

    def __init__(self, raw_data, r_type=None):
        self.raw_data = raw_data
        for attr in [
            'name', 'jid', 'state', 'release', 'ip4', 'ip6', 'orig_release',
            'boot', 'type', 'template', 'basejail', 'crt', 'res', 'qta',
            'use', 'ava', 'created', 'rsize', 'used'
        ]:
            setattr(self, attr, None)

        assert self.raw_data is not None

        if isinstance(raw_data, dict):
            for key in raw_data:
                setattr(self, key, raw_data[key])
        else:
            assert r_type is not None
            if not hasattr(self, f'{r_type}_parse'):
                raise NotImplemented

            getattr(self, f'{r_type}_parse')()

        self.normalize_values()

    # Helper parsing function
    def standard_parse(self):
        return [s.strip() for s in self.raw_data.split('|') if s.strip()]

    # Some magic method overrides
    def __repr__(self):
        if not self.name:
            return self.orig_release
        else:
            return self.name

    def __eq__(self, other):
        if not self.name:
            return other.orig_release == self.orig_release
        else:
            return other.name == self.name

    def __hash__(self):
        return hash(self.name) if self.name else hash(self.orig_release)

    # Some common normalization functions for class attributes
    def normalize_created(self):
        self.created = datetime.strptime(self.created, '%a %b %d %H:%M %Y')

    def normalize_rsize(self):
        self.rsize = self.normalize_size_values(self.rsize)

    def normalize_used(self):
        self.used = self.normalize_size_values(self.used)

    def normalize_use(self):
        self.use = self.normalize_size_values(self.use)

    def normalize_ava(self):
        self.ava = self.normalize_size_values(self.ava)

    def normalize_res(self):
        self.res = self.normalize_size_values(self.res)

    def normalize_qta(self):
        self.qta = self.normalize_size_values(self.qta)

    def normalize_template(self):
        self.template = self.template if self.template != '-' else 'z' * 99

    def normalize_release(self):
        self.orig_release = self.release
        # Assuming this is the format for now
        # "11.2-RELEASE-p6" or "11.2-RELEASE"
        release = self.release.split('-', 1)
        if len(release) == 1:
            self.release = (999, release[0])
        elif len(release) == 2:
            self.release = (float(release[0]), release[1])
        else:
            # it is of format 11.2-RELEASE-p6
            self.release = (
                float(release[0]), int(release[2][1:]), release[1]
            )

    def normalize_state(self):
        self.state = 1 if self.state == 'down' else 0

    def normalize_ip4(self):
        try:
            ip = tuple(int(c) for c in self.ip4.split('.'))
        except ValueError:
            ip = (300, self.ip4)

        self.ip4 = ip

    def normalize_boot(self):
        self.boot = 0 if self.boot == 'on' else 1

    def normalize_jid(self):
        if self.jid.isnumeric():
            self.jid = int(self.jid)
        elif self.jid == '-':
            self.jid = 99999999

    def normalize_size_values(self, value):
        try:
            return float(value.strip()[:-1]) * (10 ** self.powers[value[-1]])
        except ValueError:
            return 0

    def normalize_values(self):
        # normalize uses
        for attr in [
            a for a in dir(self)
            if not callable(a) and hasattr(self, f'normalize_{a}')
            and getattr(self, a)
        ]:
            getattr(self, f'normalize_{attr}')()

    # Function to use for sorting of RowBase Objects
    def sort_flag(self, flag):
        assert hasattr(self, flag)

        value = getattr(self, flag)
        if not isinstance(value, tuple):
            value = (value,)

        # Default to sorting to name always
        value += (self.name,)
        return value

    # PARSING FUNCTIONS
    def full_parse(self):
        # 10 columns - JID, NAME, BOOT, STATE, TYPE, RELEASE,
        # IP4, IP6, TEMPLATE, BASEJAIL
        self.jid, self.name, self.boot, self.state, self.type, \
        self.release, self.ip4, self.ip6, self.template, self.basejail = \
            self.standard_parse()

    def all_parse(self):
        # 4 columns - JID, NAME, STATE, RELEASE, IP4
        self.jid, self.name, self.state, self.release, self.ip4 = \
            self.standard_parse()

    def releases_only_parse(self):
        # 1 column - Bases Fetched
        self.release = self.standard_parse()[0]

    def quick_parse(self):
        # 2 column - NAME, IP4
        # In case of releases, it will only be one # NAME
        data = self.standard_parse()
        if len(data) == 1:
            self.release = data[0]
        else:
            self.name, self.ip4 = data

    def df_parse(self):
        self.name, self.crt, self.res, self.qta, self.use, self.ava = \
            self.standard_parse()

    def snapshot_parse(self):
        self.name, self.created, self.rsize, self.used = self.standard_parse()


class ZFS:
    # TODO: Improve how we manage zfs object here
    pool = None
    pool_mountpoint = None

    def __init__(self):
        self.set_pool()

    def set_pool(self):
        if not self.pool:
            with libzfs.ZFS() as zfs:
                pools = [
                    p for p in zfs.pools
                    if p.root_dataset.__getstate__().get(
                        'properties'
                    ).get(
                        'org.freebsd.ioc:active', {}
                    ).get('value', 'no') == 'yes'
                ]

                if pools:
                    assert len(pools) == 1, f'{len(pools)} Active pools found'

                    ZFS.pool = pools[0].name
                    ZFS.pool_mountpoint = pools[0].root_dataset.mountpoint

    @staticmethod
    def get(identifier):
        with libzfs.ZFS() as zfs:
            return zfs.get(identifier).__getstate__()

    def _zfs_get_properties(self, identifier):
        if '/' in identifier:
            dataset = self.get_dataset(identifier)

            return dataset['properties']
        else:
            pool = self.get(identifier)

            return pool['root_dataset']['properties']

    def zfs_get_property(self, identifier, key):
        try:
            return self._zfs_get_properties(identifier)[key]['value']
        except Exception:
            return '-'

    def get_dataset(self, dataset_name):
        try:
            with libzfs.ZFS() as zfs:
                return zfs.get_dataset(dataset_name).__getstate__()
        except libzfs.ZFSException:
            pass

    @staticmethod
    def get_snapshots_recursively(dataset_name):
        with libzfs.ZFS() as zfs:
            return zfs.get_dataset(dataset_name).__getstate__(
                snapshots_recursive=True
            )['snapshots_recursive']

    @staticmethod
    def get_snapshots(dataset_name):
        with libzfs.ZFS() as zfs:
            return zfs.get_dataset(dataset_name).__getstate__(
                snapshots=True
            )['snapshots']

    @staticmethod
    def get_snapshot_safely(snap):
        try:
            with libzfs.ZFS() as zfs:
                return zfs.get_snapshot(snap).__getstate__()
        except libzfs.ZFSException:
            pass

    @property
    def iocage_dataset(self):
        return self.get_dataset(f'{self.pool}/iocage')

    @property
    def releases_dataset(self):
        return self.get_dataset(f'{self.pool}/iocage/releases')

    @property
    def images_dataset_path(self):
        return os.path.join(ZFS.pool_mountpoint, 'iocage/images')


class Resource:
    DEFAULT_JSON_FILE = 'config.json'

    def __init__(self, name, zfs=None):
        self.name = name
        self.zfs = ZFS() if not zfs else zfs
        assert isinstance(self.zfs, ZFS) is True

    def __repr__(self):
        return self.name

    def convert_to_row(self, **kwargs):
        raise NotImplemented


class Snapshot(Resource):

    def __init__(self, name, parent_dataset, zfs=None):
        super().__init__(name, zfs)
        self.parent = parent_dataset
        if isinstance(self.parent, str):
            self.parent = Jail(self.parent)
        if self.exists:
            for k, v in self.zfs.get_snapshot_safely(self.name).items():
                setattr(self, k, v)

    @property
    def exists(self):
        return self.zfs.get_snapshot_safely(self.name) is not None

    def convert_to_row(self, **kwargs):
        full = kwargs.get('full', False)
        if full:
            name = self.id
        else:
            name = self.id.split('@')[-1]
            # If snap is of root dataset - we add /root
            if self.id.split('/')[-1].split('@')[0] == 'root':
                name += '/root'

        return Row({
            'name': name,
            'created': self.properties['creation']['value'],
            'rsize': self.properties['referenced']['value'],
            'used': self.properties['used']['value']
        })


class Release(Resource):

    @property
    def exists(self):
        return self.name in [
            r['name'].split('/')[-1]
            for r in self.zfs.releases_dataset['children']
        ]

    def convert_to_row(self, **kwargs):
        return Row({'release': self.name})


# A simple class which can tell us the state of the jail
class Jail(Resource):

    def convert_to_row(self, **kwargs):
        short_name = kwargs.get('short_name', True)
        full = kwargs.get('full', False)

        props = self.jail_dataset['properties']

        ip4 = self.config.get('ip4_addr', 'none')
        if self.config.get('dhcp', 'off') == 'on':
            ip4 = 'DHCP'

        if ip4 == 'none':
            ip4 = '-'

        if full:
            release = self.release
        else:
            release = '-'.join(self.release.rsplit('-')[:2])

        template = '-'
        jail_origin = self.root_dataset['properties']['origin']['value']
        if jail_origin:
            template = jail_origin.rsplit(
                '/root@', 1
            )[0].rsplit('/', 1)[-1]
            if any(
                    v in template.lower()
                    for v in ('release', 'stable')
            ):
                template = '-'

        return Row({
            'name': self.short_name if short_name else self.name,
            'jid': self.jid,
            'state': 'up' if self.running else 'down',
            'boot': self.config.get('boot', 'off'),
            'type': 'jail' if not self.is_template else 'template',
            # TODO: Add support for plugins
            'ip6': '-',  # FIXME: Change when ip6 tests are added
            'basejail': 'yes' if self.is_basejail else 'no',
            'crt': props['compressratio']['value'],
            'res': props['reservation']['value'],
            'qta': props['quota']['value'],
            'use': props['used']['value'],
            'ava': props['available']['value'],
            'ip4': ip4,
            'release': release,
            'template': template
        })

    @property
    def path(self):
        # Jail can be either under `jails` or `templates` datasets
        if self.zfs.get_dataset(
                f'{self.zfs.pool}/iocage/jails/{self.name}'
        ):
            dataset = 'jails'
        else:
            dataset = 'templates'
        return f'{self.zfs.pool}/iocage/{dataset}/{self.name}'

    @property
    def absolute_path(self):
        return self.jail_dataset['mountpoint']

    @property
    def jail_dataset(self):
        return self.zfs.get_dataset(self.path)

    @property
    def root_dataset(self):
        return self.zfs.get_dataset(
            os.path.join(self.path, 'root')
        )

    @property
    def recursive_snapshots(self):
        immediate_snaps = [
            s['id'].split('@')[1] for s in self.zfs.get_snapshots(self.path)
        ]

        return [
            Snapshot(s['id'], self, self.zfs)
            for s in self.zfs.get_snapshots_recursively(self.path)
            if s['id'].split('@')[1] in immediate_snaps
            # The last if is for logic copied from iocage
        ]

    @property
    def exists(self):
        return self.zfs.get_dataset(self.path) is not None

    @property
    def is_template(self):
        return 'iocage/templates/' in self.path

    @property
    def jid(self):
        try:
            return int(
                subprocess.check_output(
                    ['jls', '-j', f'ioc-{self.name.replace(".", "_")}'],
                    stderr=subprocess.PIPE
                ).decode('utf-8').split()[5]
            )
        except subprocess.CalledProcessError:
            return None

    @property
    def running(self):
        return self.jid is not None

    @property
    def config(self):
        # TODO: Let's add validation for props as well in future
        config = None
        if os.path.exists(os.path.join(
                self.absolute_path, self.DEFAULT_JSON_FILE
        )):
            with open(
                os.path.join(self.absolute_path, self.DEFAULT_JSON_FILE), 'r'
            ) as f:
                try:
                    config = json.loads(f.read())
                except json.JSONDecodeError:
                    pass

        assert config is not None, f'Failed to read config.json for {self.name}'

        return config

    @property
    def fstab(self):
        # Let's return a list of fstab lines
        fstab = None
        if os.path.exists(os.path.join(
            self.absolute_path, 'fstab'
        )):
            with open(os.path.join(self.absolute_path, 'fstab'), 'r') as f:
                fstab = [
                    l.split('#')[0].strip().replace('\t', ' ')
                    for l in f.readlines() if l
                ]

        assert fstab is not None

        return fstab

    @property
    def release(self):
        return self.config.get('release', 'EMPTY')

    @property
    def is_thickconfig(self):
        return 'CONFIG_TYPE' in self.config

    @property
    def is_basejail(self):
        return self.config.get('basejail', 'no') == 'yes'

    @property
    def is_empty(self):
        return self.config.get('release', 'EMPTY') == 'EMPTY'

    @property
    def is_thickjail(self):
        return not self.root_dataset[
            'properties'
        ].get('origin', {}).get('value')

    @property
    def is_rcjail(self):
        return self.config.get('boot', 'off') == 'on'

    @property
    def ip(self):
        assert self.running is True
        try:
            # TODO: we should probably load interface from config and
            # make changes if necessary to it's value then
            # TODO: Discuss with Brandon about support for older releases
            return subprocess.check_output(
                ['jexec', f'ioc-{self.name}', 'ifconfig', 'epair0b', 'inet']
            ).decode().splitlines()[2].split()[1]
        except subprocess.CalledProcessError:
            pass

    @property
    def short_name(self):
        try:
            return str(uuid.UUID(self.name, version=4))[:8]
        except ValueError:
            return self.name


class ResourceSelector:

    # TODO: Probably come up with a better strategy for filtering
    def __init__(self):
        self.zfs = ZFS()

    @property
    def iocage_dataset(self):
        return self.zfs.iocage_dataset

    @property
    def jails_dataset(self):
        return self.zfs.get_dataset(
            f'{self.iocage_dataset["name"]}/jails'
        )

    @property
    def templates_dataset(self):
        return self.zfs.get_dataset(
            f'{self.iocage_dataset["name"]}/templates'
        )

    def filter_jails(self, filters):
        # is_template, running, startable, is_thickconfig, is_basejails
        # is_thickjail, is_rcjail
        # TODO: Complete this
        return [
            Jail(d.name.split('/')[-1])
            for d in itertools.chain(
                self.jails_dataset.children, self.templates_dataset.children
            )
        ]

    @property
    def all_jails(self):
        return [
            Jail(d['name'].split('/')[-1], self.zfs)
            for d in itertools.chain(
                self.jails_dataset['children'],
                self.templates_dataset['children']
            )
        ]

    @property
    def releases(self):
        return [
            Release(c['name'].split('/')[-1])
            for c in self.zfs.releases_dataset['children']
        ]

    @property
    def jails(self):
        return [j for j in self.all_jails if not j.is_template]

    @property
    def all_jails_having_snapshots(self):
        return [j for j in self.all_jails if j.recursive_snapshots]

    @property
    def jails_having_snapshots(self):
        return [j for j in self.jails if j.recursive_snapshots]

    @property
    def templates_having_snapshots(self):
        return [j for j in self.template_jails if j.recursive_snapshots]

    @property
    def running_jails(self):
        return [j for j in self.all_jails if j.running]

    @property
    def stopped_jails(self):
        return [j for j in self.all_jails if not j.running]

    @property
    def template_jails(self):
        return [j for j in self.all_jails if j.is_template]

    @property
    def thickconfig_jails(self):
        return [j for j in self.all_jails if j.is_thickconfig]

    @property
    def basejails(self):
        return [j for j in self.all_jails if j.is_basejail]

    @property
    def thickjails(self):
        return [j for j in self.all_jails if j.is_thickjail]

    @property
    def rcjails(self):
        return [j for j in self.all_jails if j.is_rcjail]

    @property
    def jails_with_snapshots(self):
        return [j for j in self.all_jails if j.recursive_snapshots]

    @property
    def startable_jails(self):
        return [
            j for j in self.all_jails
            if not j.is_template and not j.is_empty
        ]

    @property
    def startable_jails_and_not_running(self):
        # TODO: Let's improve this - with internal filters
        return [j for j in self.startable_jails if not j.running]
