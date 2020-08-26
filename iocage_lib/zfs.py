import itertools
import os
import subprocess

from collections import defaultdict


def run(command, **kwargs):
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    kwargs.setdefault('encoding', 'utf8')
    check = kwargs.pop('check', True)
    proc = subprocess.Popen(command, **kwargs)
    stdout, stderr = proc.communicate()
    cp = subprocess.CompletedProcess(
        command, proc.returncode, stdout=stdout, stderr=stderr
    )
    if check:
        try:
            cp.check_returncode()
        except subprocess.CalledProcessError:
            raise ZFSException(cp.returncode, cp.stderr)
    return cp


class ZFSException(Exception):
    def __init__(self, code, message):
        super(Exception, self).__init__(message)
        self.code = code

    def __reduce__(self):
        return self.__class__, (self.code, self.args)


IOCAGE_POOL_PROP = 'org.freebsd.ioc:active'


def list_pools():
    return list(filter(
        lambda v: v,
        run(['zpool', 'list', '-H', '-o', 'name']).stdout.split('\n')
    ))


def pool_health(pool):
    return run(['zpool', 'list', '-H', '-o', 'health', pool]).stdout.strip()


def properties(dataset, resource_type='zfs'):
    return {
        v.split()[0].strip(): v.split(maxsplit=1)[-1].strip()
        if len(v.split()) > 1 else '-'
        for v in run([
            resource_type, 'get', '-H', '-o', 'property,value', 'all', dataset
        ]).stdout.split('\n')
        if v
    }


def all_properties(
    path='', resource_type='zfs', depth=None, recursive=False, types=None
):
    flags = []
    if depth:
        flags.extend(['-d', str(depth)])
    if recursive:
        flags.append('-r')
    if types:
        flags.extend(['-t', ','.join(types)])

    data = run(list(filter(
        bool, [
            resource_type, 'get', '-H', '-o', 'name,property,value',
            *flags, 'all', path
        ]
    ))).stdout.split('\n')
    fs = defaultdict(dict)
    for line in filter(bool, data):
        name, prop = line.split('\t')[:2]
        fs[name.strip()][prop.strip()] = line.split(
            '\t', maxsplit=2
        )[-1].strip()

    return fs


def dataset_properties(dataset):
    return properties(dataset, 'zfs')


def pool_properties(pool):
    return properties(pool, 'zpool')


def iocage_activated_pool():
    for pool in list_pools():
        if dataset_properties(pool).get('org.freebsd.ioc:active') == 'yes':
            return pool
    else:
        return None


def iocage_activated_dataset():
    pool = iocage_activated_pool()
    if pool:
        if os.path.join(pool, 'iocage') in get_dependents(pool, depth=1):
            return os.path.join(pool, 'iocage')

    return None


def get_all_dependents():
    return get_dependents('')


def get_dependents(identifier, depth=None, filters=None):
    filters = filters or ['-t', 'filesystem']
    id_depth = len(identifier.split('/'))
    try:
        return list(
            filter(
                lambda p: p and (p if not depth else len(
                    p.split('/')
                ) - id_depth <= depth and len(p.split('/')) - id_depth),
                run(
                    ['zfs', 'list'] + filters + ['-rHo', 'name'] + (
                        [identifier] if identifier else []),
                ).stdout.split('\n')
            )
        )
    except ZFSException:
        return []


def set_property(dataset, prop, value, resource_type='zfs'):
    run([resource_type, 'set', f'{prop}={value}', dataset])


def set_dataset_property(dataset, prop, value):
    set_property(dataset, prop, value, 'zfs')


def set_pool_property(pool, prop, value):
    set_property(pool, prop, value, 'zpool')


def create_dataset(data):
    flags = []
    if data.get('create_ancestors'):
        flags.append('-p')

    return run([
        'zfs', 'create', *flags, *itertools.chain.from_iterable(
            ('-o', f'{k}={v}') for k, v in data.get('properties', {}).items()
        ), data['name']
    ]).returncode == 0


def list_snapshots(raise_error=True, resource=None, recursive=False):
    flags = []
    if recursive:
        if not resource:
            raise ZFSException(1, 'Resource must be specified with recursive')
        flags.append('-r')

    return filter(
        bool,
        map(
            str.strip,
            run([
                'zfs', 'list', '-H', *flags, '-t', 'snapshot', '-o', 'name',
                *([resource] if resource else [])
            ], check=raise_error).stdout.split('\n')
        )
    )


def destroy_zfs_resource(resource, recursive=False, force=False):
    cmd = ['zfs', 'destroy']
    if recursive:
        cmd.append('-r')
    if force:
        cmd.append('-Rf')
    return run([*cmd, resource]).returncode == 0


def mount_dataset(dataset):
    return run(['zfs', 'mount', dataset]).returncode == 0


def umount_dataset(dataset, force=True):
    return run(
        ['zfs', 'umount', *(['-f' if force else '']), dataset]
    ).returncode == 0


def get_dataset_from_mountpoint(path):
    return run(
        ['zfs', 'get', '-H', '-o', 'value', 'name', path]
    ).stdout.strip()


def rename_dataset(old_name, new_name, options=None):
    flags = []
    options = options or {}
    if options.get('force_unmount'):
        flags.append('-f')

    return run(['zfs', 'rename', *flags, old_name, new_name]).returncode == 0


def rollback_snapshot(snap, options=None):
    flags = []
    options = options or {}
    if options.get('destroy_latest'):
        flags.append('-r')

    return run(['zfs', 'rollback', *flags, snap]).returncode == 0


def create_snapshot(snap, options=None):
    flags = []
    options = options or {}
    if options.get('recursive'):
        flags.append('-r')

    return run(['zfs', 'snapshot', *flags, snap])


def dataset_exists(dataset):
    return run(['zfs', 'list', dataset], check=False).returncode == 0


def clone_snapshot(snapshot, dataset):
    return run(['zfs', 'clone', snapshot, dataset]).returncode == 0


def promote_dataset(dataset):
    return run(['zfs', 'promote', dataset]).returncode == 0


def inherit_property(dataset, ds_property):
    return run(['zfs', 'inherit', ds_property, dataset]).returncode == 0
