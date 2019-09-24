import itertools
import os
import subprocess


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
        v.split()[0].strip(): v.split()[1].strip()
        if len(v.split()) > 1 else '-'
        for v in run(
            [resource_type, 'get', '-H', '-o', 'property,value', 'all', dataset]
        ).stdout.split('\n')
        if v
    }


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
        if 'iocage' in get_dependents(pool, depth=1):
            return os.path.join(pool, 'iocage')

    return None


def get_dependents(identifier, depth=None):
    id_depth = len(identifier.split('/'))
    try:
        return list(
            filter(
                lambda p: p if not depth else len(
                    p.split('/')
                ) - id_depth <= depth and len(p.split('/')) - id_depth,
                run(
                    ['zfs', 'list', '-rHo', 'name', identifier],
                ).stdout.split()
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

    return run([
        'zfs', 'list', '-H', *flags, '-t', 'snapshot', '-o', 'name',
        *([resource] if resource else [])
    ], check=raise_error).stdout


def destroy_zfs_resource(resource, recursive=False, force=False):
    cmd = ['zfs', 'destroy']
    if recursive:
        cmd.append('-r')
    if force:
        cmd.append('-Rf')
    return run([*cmd, resource]).returncode == 0


def mount_dataset(dataset):
    return run(['zfs', 'mount', dataset]).returncode == 0


def umount_dataset(dataset):
    return run(['zfs', 'umount', dataset]).returncode == 0


def get_dataset_from_mountpoint(path):
    return run(['zfs', 'get', '-H', '-o', 'name', path]).stdout.strip()