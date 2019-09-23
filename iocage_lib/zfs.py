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


def dataset_properties(dataset):
    return {
        v.split()[0].strip(): v.split()[1].strip()
        if len(v.split()) > 1 else '-'
        for v in run(
            ['zfs', 'get', '-H', '-o', 'property,value', 'all', dataset]
        ).stdout.split('\n')
        if v
    }


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


def set_dataset_property(dataset, prop, value):
    run(['zfs', 'set', f'{prop}={value}', dataset])
