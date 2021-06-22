# Copyright (c) 2014-2019, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Common methods we reuse."""
import collections
import contextlib
import ipaddress
import logging
import os
import shutil
import stat
import subprocess as su
import tempfile as tmp

import jsonschema
import requests
import datetime as dt
import re
import shlex
import glob
import netifaces
import concurrent.futures
import json
import urllib.parse

import iocage_lib.ioc_exceptions
import iocage_lib.ioc_exec
from iocage_lib.cache import cache

from iocage_lib.dataset import Dataset

INTERACTIVE = False
# 4 is a magic number for default and doesn't refer
# to the actual ruleset 4 in devfs.rules(!)
IOCAGE_DEVFS_RULESET = 4


def callback(_log, callback_exception):
    """Helper to call the appropriate logging level"""
    log = logging.getLogger('iocage')
    level = _log['level']
    message = _log['message']
    force_raise = _log.get('force_raise')
    suppress_log = _log.get('suppress_log')

    if level == 'CRITICAL':
        log.critical(message)
    elif level == 'ERROR':
        log.error(message)
    elif level == 'WARNING':
        log.warning(message)
    elif level == 'INFO':
        log.info(message)
    elif level == 'DEBUG':
        log.debug(message)
    elif level == 'VERBOSE':
        log.log(15, message)
    elif level == 'NOTICE':
        log.log(25, message)
    elif level == 'EXCEPTION':
        if not INTERACTIVE:
            raise callback_exception(message)
        else:
            if not isinstance(message, str) and isinstance(
                message,
                collections.Iterable
            ):
                message = '\n'.join(message)

            if not suppress_log:
                log.error(message)

            if force_raise:
                raise callback_exception(message)
            else:
                raise SystemExit(1)


def logit(content, _callback=None, silent=False, exception=RuntimeError):
    """Helper to check callable status of callback or call ours."""
    if silent and callable(_callback) and content['level'] != 'EXCEPTION':
        # Send these through for completeness to library consumers
        _callback(content, exception)
    elif silent and content['level'] != "EXCEPTION":
        # They need to see these errors, too bad!
        return

    if content['level'] == "EXCEPTION":
        callback(content, exception)

    # This will log with our callback method if they didn't supply one.
    _callback = _callback if callable(_callback) else callback
    _callback(content, exception)


def try_convert(value, default, *types):
    for t in types:
        try:
            return t(value)
        except (ValueError, TypeError):
            continue

    return default


def raise_sort_error(sort_list):
    msg = "Invalid sort type specified, use one of:\n"

    for s in sort_list:
        msg += f"  {s}\n"

    logit({"level": "EXCEPTION", "message": msg.rstrip()})


def ioc_sort(caller, s_type, data=None):
    try:
        s_type = s_type.lower()
    except AttributeError:
        # When a failed template is attempted, it will set s_type to None.
        s_type = "name"

    sort_funcs = {
        "jid": sort_jid,
        "name": sort_name,
        "boot": sort_boot,
        "state": sort_state,
        "type": sort_type,
        "release": sort_release,
        "ip4": sort_ip,
        "ip6": sort_ip6,
        "template": sort_template,
        "crt": sort_crt,
        "res": sort_res,
        "qta": sort_qta,
        "use": sort_use,
        "ava": sort_ava,
        "created": sort_created,
        "rsize": sort_res,
        "used": sort_qta,
        "key": sort_key
    }

    list_full_sorts = [
        "jid", "name", "boot", "state", "type", "release", "ip4", "ip6",
        "template"
    ]
    list_short_sorts = ["jid", "name", "state", "release", "ip4"]
    df_sorts = ["name", "crt", "res", "qta", "use", "ava"]
    snaplist_sorts = ["name", "created", "rsize", "used"]

    if caller == "list_full" and s_type not in list_full_sorts:
        raise_sort_error(list_full_sorts)
    elif caller == "list_short" and s_type not in list_short_sorts:
        raise_sort_error(list_short_sorts)
    elif caller == "df" and s_type not in df_sorts:
        raise_sort_error(df_sorts)
    elif caller == "snaplist" and s_type not in snaplist_sorts:
        raise_sort_error(snaplist_sorts)

    # Most calls will use this

    if caller == "list_release" and s_type == "release":
        return sort_release(data, split=True)

    return sort_funcs.get(s_type)


def get_natural_sortkey(text):
    # attempt to convert str to int to facilitate simplified natural sorting
    # integers will be ranked before alphanumerical values
    if text is None:
        return 30, None
    try:
        return 10, int(text)
    except ValueError:
        return 20, text


def get_name_sortkey(name):
    # We want to properly sort names that have been created with count > 1
    _sort = name.strip().rsplit('_', 1)

    if len(_sort) > 1:
        # snaplist may have a /root suffix
        _numb = _sort[1].rsplit("/", 1)
        _path = _numb[1] if len(_numb) > 1 else ""
        return (_sort[0],) + get_natural_sortkey(_numb[0]) + (_path,)
    else:
        return name, 0


def get_size_sortkey(size):
    # assume the size is in powers of 10 (KB) as opposed to powers of 2 (KiB)
    powers = {
        "B": 0,
        "K": 3,
        "M": 6,
        "G": 9,
        "T": 12,
        "P": 15
    }
    try:
        return float(size[:-1]) * (10 ** powers[size[-1]])
    except ValueError:
        return 0


def sort_created(crt):
    """Sort snaplist by CREATED"""

    try:
        _timestmp = dt.datetime.strptime(crt[1], '%a %b %d %H:%M %Y')
    except ValueError:
        _timestmp = crt[1]
    return (_timestmp,) + get_name_sortkey(crt[0])


def sort_crt(crt):
    """Sort df by CRT"""

    return (crt[1],) + get_name_sortkey(crt[0])


def sort_res(res):
    """Sort df by RES or snaplist by RSIZE"""

    return (get_size_sortkey(res[2]),) + get_name_sortkey(res[0])


def sort_qta(qta):
    """Sort df by QTA or snaplist by USED"""

    return (get_size_sortkey(qta[3]),) + get_name_sortkey(qta[0])


def sort_use(use):
    """Sort df by USE"""

    return (get_size_sortkey(use[4]),) + get_name_sortkey(use[0])


def sort_ava(ava):
    """Sort df by AVA"""

    return (get_size_sortkey(ava[5]),) + get_name_sortkey(ava[0])


def sort_ip6(ip):
    """Helper for sort_ip"""

    return sort_ip(ip, version="6")


def sort_ip(sort_row, version='4'):
    """
    Sort the list by IP address
    We expect the following values for ip sorting
    1) interface|ip/subnet
    2) interface|ip
    3) interface|dhcp
    4) ip
    5) ip|accept_rtadv

    All the while obviously not forgetting that there can be multiple
    ips specified by ',' delimiter
    """
    list_length = len(sort_row)

    # Length 9 is list -l, 10 is list -P
    # Length 5 is list
    if version == '4':
        ip_check = ipaddress.IPv4Network
    else:
        ip_check = ipaddress.IPv6Network

    if list_length in (9, 10):
        ip = sort_row[6] if version == '4' else sort_row[7]
    elif list_length == 5:
        ip = sort_row[4]
    else:
        ip = sort_row

    if not isinstance(ip, list):
        # Let's normalize the ip list first
        ip_list = list(
            map(
                lambda v: ip_check(v),
                filter(
                    lambda v: try_convert(v, None, ip_check),
                    map(
                        lambda v: v.split('|')[1].split('/')[0].strip()
                        if '|' in v else
                        v.split('/')[0].strip(),
                        ip.split(',')
                    )
                )
            )
        )

        if ip_list:
            ip_list.sort()
            ip = tuple(
                int(c)
                for c in str(ip_list[0]).split('/')[0].split(
                    '.' if version == '4' else ':'
                )
            )
            if version != '4':
                ip = (0,) + ip
        else:
            ip = (9999, ip)

        ip = ip + get_name_sortkey(sort_row[1])

    return ip


def sort_type(jail_type):
    """Sort the list by jail type, then by name."""

    return (jail_type[4],) + get_name_sortkey(jail_type[1])


def sort_state(state):
    """Sort the list by state, then by name."""
    list_length = len(state)

    # Length 9 is list -l, 10 is list -P
    # Length 5 is list

    if list_length == 9 or list_length == 10:
        _state = 0 if state[3] != "down" else 1
    elif list_length == 5:
        _state = 0 if state[2] != "down" else 1
    else:
        _state = state

    # 0 is up, 1 is down, lame hack to get running jails on top.
    # jails will be sorted by name within state
    return (_state,) + get_name_sortkey(state[1])


def sort_boot(boot):
    """Sort the list by boot, then by name."""
    # Lame hack to get on above off.
    # 0 is on, 1 is off
    _boot = 0 if check_truthy(boot[2]) else 1
    return (_boot,) + get_name_sortkey(boot[1])


def sort_jid(jid):
    """Sort the list by JID."""

    return get_natural_sortkey(jid[0]) + get_name_sortkey(jid[1])


def sort_name(name):
    """Sort list by the name."""

    if not isinstance(name, str):
        list_length = len(name)
        # Length 9 is list -l, 10 is list -P, 5 is list (normal)
        # Length 4 is snaplist or list -PR
        # Length 6 is df
        if list_length == 4 or list_length == 6:
            name = name[0]
        else:
            name = name[1]

    return get_name_sortkey(name)


def sort_key(item):
    """Sort list by the first key."""
    if len(item) != 1:
        item = item[0]
    return (list(item.keys())[0],)


def sort_template(template):
    """Helper function for templates to be sorted in sort_name"""
    # Ugly hack to have templates listed first, this assumes they will not
    # name their template with this string, it would be *remarkable* if they
    # did.
    _template = template[8] if template[8] != "-" else "z" * 999999

    return sort_name(_template) + get_name_sortkey(template[1])


def sort_release(releases, split=False, fetch_releases=False):
    """
    Sort the list by RELEASE, if split is true it's expecting full
    datasets.
    """
    r_dict = {}
    release_list = []
    list_sort = False

    try:
        # Length 9 (standard) or 10 (plugins) is list -l,
        # Length 5 is list

        length = len(releases)

        if fetch_releases:
            pass
        elif length == 9 or length == 10:
            # Attempt to split off the -p* stuff.
            try:
                _release, _patch = releases[5].rsplit("-p", 1)
            except ValueError:
                _release = releases[5]
                _patch = 0
            list_sort = True
        elif length == 5:
            _release = releases[3]
            _patch = 0
            list_sort = True
    except TypeError:
        # This is list -r
        pass

    if split:
        for i, rel in enumerate(releases):
            try:
                rel, r_type = rel.properties["mountpoint"].rsplit("/")[
                    -1].split("-", 1)
            except ValueError:
                # Non-standard naming scheme
                rel = rel.properties["mountpoint"].rsplit("/")[
                    -1].split("-", 1)[0]
                r_type = ''

            if len(rel) > 2 and r_type:
                try:
                    rel = float(rel)
                except ValueError:
                    # Non-standard naming scheme
                    pass

            # enumeration ensures 11.2-LOCAL does not take the place of 11.2-R
            r_dict[f'{rel}_{i}'] = r_type
    else:
        if list_sort:
            _release = _release.split("-", 1)
            try:
                _version = float(_release[0])
                _patch = int(_patch)
                return (_version, _patch, _release[1]) \
                    + get_name_sortkey(releases[1])
            except ValueError:
                return (999, _release[0]) + get_name_sortkey(releases[1])

        else:
            for release in releases:
                if not isinstance(release, str):
                    release = release.name

                try:
                    release, r_type = release.split("-", 1)

                    if len(release) > 2:
                        release = float(release)

                    r_dict[release] = r_type
                except ValueError:
                    pass

    ordered_r_dict = collections.OrderedDict(sorted(r_dict.items()))
    index = 0

    for r, t in ordered_r_dict.items():
        if split:
            r = r.rsplit('_')[0]  # Remove the enumeration
            if t:
                release_list.insert(index, [f"{r}-{t}"])
            else:
                release_list.insert(index, [r])
            index += 1
        else:
            release_list.insert(index, f"{r}-{t}")
            index += 1

    return release_list


# Cyrille Pontvieux on StackOverflow
def copytree(src, dst, symlinks=False, ignore=None):
    """Copies a tree and overwrites."""

    if not os.path.exists(dst):
        os.makedirs(dst)
        shutil.copystat(src, dst)
    lst = os.listdir(src)

    if ignore:
        excl = ignore(src, lst)
        lst = [x for x in lst if x not in excl]

    for item in lst:
        s = os.path.join(src, item)
        d = os.path.join(dst, item)

        if symlinks and os.path.islink(s):
            if os.path.lexists(d):
                os.remove(d)
            os.symlink(os.readlink(s), d)
            try:
                st = os.lstat(s)
                mode = stat.S_IMODE(st.st_mode)
                os.lchmod(d, mode)
            except Exception:
                pass  # lchmod not available
        elif os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


# http://stackoverflow.com/questions/2333872/atomic-writing-to-file-with-python
@contextlib.contextmanager
def tempfile(suffix='', dir=None):
    """
    Context for temporary file.

    Will find a free temporary filename upon entering
    and will try to delete the file on leaving, even in case of an exception.

    Parameters
    ----------
    suffix : string
        optional file suffix
    dir : string
        optional directory to save temporary file in
    """

    tf = tmp.NamedTemporaryFile(delete=False, suffix=suffix, dir=dir)
    tf.file.close()
    try:
        yield tf.name
    finally:
        try:
            os.remove(tf.name)
        except OSError as e:
            if e.errno == 2:
                pass
            else:
                raise


@contextlib.contextmanager
def open_atomic(filepath, *args, **kwargs):
    """
    Open temporary file object that atomically moves to destination upon
    exiting.

    Allows reading and writing to and from the same filename.

    The file will not be moved to destination in case of an exception.

    Parameters
    ----------
    filepath : string
        the file path to be opened
    fsync : bool
        whether to force write the file to disk
    *args : mixed
        Any valid arguments for :code:`open`
    **kwargs : mixed
        Any valid keyword arguments for :code:`open`
    """
    fsync = kwargs.get('fsync', False)

    with tempfile(dir=os.path.dirname(os.path.abspath(filepath))) as tmppath:
        with open(tmppath, *args, **kwargs) as file:
            try:
                yield file
            finally:
                if fsync:
                    file.flush()
                    os.fsync(file.fileno())
        os.rename(tmppath, filepath)
        os.chmod(filepath, 0o644)


def get_nested_key(_dict, keys=None):
    """Gets a nested key from a dictionary."""

    if not keys:
        keys = []

    key = keys.pop(0)

    if len(keys) == 0:
        return _dict[key]

    return get_nested_key(_dict[key], keys)


def checkoutput(*args, **kwargs):
    """Just a wrapper to return utf-8 from check_output"""
    try:
        out = su.check_output(*args, **kwargs)

        out = out.decode('utf-8')
    except su.CalledProcessError:
        raise

    return out


def set_rcconf(jail_path, key, value):
    conf_file = f"{jail_path}/root/etc/rc.conf"

    found = False
    changed = False

    with open(conf_file, "r+") as f:

        output = []

        lines = f.read().splitlines()

        for line in lines:

            try:
                current_key, current_value = line.split("=", 1)
                current_value = current_value.strip("\"")
            except ValueError:
                output.append(line)

                continue

            if current_key == key:
                found = True

                if current_value != value:
                    changed = True
                    output.append(f"{key}=\"{value}\"")

                    continue

            output.append(line)

        if not found:
            output.append(f"{key}=\"{value}\"")
            changed = True

        if changed:
            f.seek(0)
            f.write("\n".join(output) + "\n")
            f.truncate()


def parse_latest_release():
    """
    Returns the latest RELEASE from upstreams supported list
    """
    logging.getLogger("requests").setLevel(logging.WARNING)
    sup = "https://www.freebsd.org/security/index.html#sup"
    req = requests.get(sup)
    status = req.status_code == requests.codes.ok
    sup_releases = []

    if not status:
        req.raise_for_status()

    for rel in req.content.decode("iso-8859-1").split():
        rel = rel.strip("href=").strip("/").split(">")
        # We want a dynamic supported
        try:
            if "releng/" in rel[1]:
                rel = rel[1].strip('</td').strip("releng/")

                if rel not in sup_releases:
                    sup_releases.append(rel)
        except IndexError:
            pass

    latest = f"{sorted(sup_releases)[-1]}-RELEASE"

    return latest


def get_host_release():
    """Helper to return the hosts sanitized RELEASE"""
    rel = os.uname()[2]
    release = rel.rsplit("-", 1)[0]

    if "-STABLE" in rel:
        # FreeNAS
        release = f"{release}-RELEASE"
    elif "-HBSD" in rel:
        # HardenedBSD
        release = re.sub(r"\W\w.", "-", release)
        release = re.sub(r"([A-Z])\w+", "STABLE", release)
    elif "-RELEASE" not in rel:
        release = "Not a RELEASE"

    return release


def check_release_newer(
    release, callback=None, silent=False, raise_error=True, major_only=False
):
    """Checks if the host RELEASE is greater than the target release"""
    host_release = get_host_release()

    if host_release == "Not a RELEASE":
        return

    h_float = float(str(host_release).rsplit('.' if major_only else '-')[0])
    r_float = float(str(release).rsplit('.' if major_only else '-')[0])

    if h_float < r_float and raise_error:
        logit(
            {
                "level": "EXCEPTION",
                "message": f"\nHost: {host_release} is not greater"
                f" than target: {release}\nThis is unsupported."
            },
            _callback=callback,
            silent=silent)

    return h_float < r_float


def generate_devfs_ruleset(conf, paths=None, includes=None, callback=None,
                           silent=False):
    """
    Will add a per jail devfs ruleset with the specified rules,
    specifying defaults that equal devfs_ruleset 4
    """
    configured_ruleset = conf['devfs_ruleset']
    devfs_includes = []
    devfs_rulesets = su.run(
        ['devfs', 'rule', 'showsets'],
        stdout=su.PIPE, universal_newlines=True
    )
    ruleset_list = [int(i) for i in devfs_rulesets.stdout.splitlines()]

    ruleset = int(conf["min_dyn_devfs_ruleset"])
    while ruleset in ruleset_list:
        ruleset += 1
    ruleset = str(ruleset)

    # Custom devfs_ruleset configured, clone to dynamic ruleset
    if int(configured_ruleset) != IOCAGE_DEVFS_RULESET:
        if int(configured_ruleset) != 0 and int(configured_ruleset) not in ruleset_list:
            return True, configured_ruleset, '-1'
        rules = su.run(
            ['devfs', 'rule', '-s', str(configured_ruleset), 'show'],
            stdout=su.PIPE, universal_newlines=True
        )
        for rule in rules.stdout.splitlines():
            su.run(['devfs', 'rule', '-s', ruleset, 'add'] +
                   rule.split(' ')[1:], stdout=su.PIPE)

        return (True, configured_ruleset, ruleset)

    # Create default ruleset
    devfs_dict = dict((dev, None) for dev in (
        'hide', 'null', 'zero', 'crypto', 'random', 'urandom', 'ptyp*',
        'ptyq*', 'ptyr*', 'ptys*', 'ptyP*', 'ptyQ*', 'ptyR*', 'ptyS*', 'ptyl*',
        'ptym*', 'ptyn*', 'ptyo*', 'ptyL*', 'ptyM*', 'ptyN*', 'ptyO*', 'ttyp*',
        'ttyq*', 'ttyr*', 'ttys*', 'ttyP*', 'ttyQ*', 'ttyR*', 'ttyS*', 'ttyl*',
        'ttym*', 'ttyn*', 'ttyo*', 'ttyL*', 'ttyM*', 'ttyN*', 'ttyO*', 'ptmx',
        'pts', 'pts/*', 'fd', 'fd/*', 'stdin', 'stdout', 'stderr', 'zfs'
    ))

    # We set these up by default above
    skip_includes = ['$devfsrules_hide_all', '$devfsrules_unhide_basic',
                     '$devfsrules_unhide_login']
    if includes is not None:
        devfs_includes = [include for include in includes if include not in
                          skip_includes]

    if paths is not None:
        devfs_dict.update(paths)

    # We may end up setting all of these.
    if check_truthy(conf['allow_mount_fusefs']):
        devfs_dict['fuse'] = None
    if check_truthy(conf['bpf']):
        devfs_dict['bpf*'] = None
    if check_truthy(conf['allow_tun']):
        devfs_dict['tun*'] = None

    for include in devfs_includes:
        su.run(
            ['devfs', 'rule', '-s', ruleset, 'add', 'include', include],
            stdout=su.PIPE
        )

    for path, mode in devfs_dict.items():
        # # Default hide all
        if path == 'hide':
            su.run(
                ['devfs', 'rule', '-s', ruleset, 'add', 'hide'],
                stdout=su.PIPE
            )
            continue

        path = ['add', 'path', path]

        if mode is not None:
            path += [mode]
        else:
            path += ['unhide']

        su.run(['devfs', 'rule', '-s', ruleset] + path, stdout=su.PIPE)

    return (False, configured_ruleset, ruleset)


def runscript(script, custom_env=None):
    """
    Runs the script provided and return a tuple with first value showing
    stdout and last showing stderr
    """
    script = shlex.split(script)

    if len(script) > 1:
        # We may be getting ';', '&&' and so forth. Adding the shell for
        # safety.
        script = ['/bin/sh', '-c', ' '.join(script)]
    elif os.access(script[0], os.X_OK):
        script = script[0]
    else:
        return None, 'Script is not executable!'

    try:
        output = iocage_lib.ioc_exec.SilentExec(
            script, None, unjailed=True, decode=True, su_env=custom_env
        )
    except iocage_lib.ioc_exceptions.CommandFailed as e:
        return None, f'Script returned non-zero status: {e}'
    else:
        return output.stdout.rstrip('\n'), None


def match_to_dir(iocroot, uuid, old_uuid=None):
    """
    Checks for existence of jail/template with specified uuid.
    Replaces dots and underscores in the uuid with pattern [._] and returns
    the template- or jail directory that matches, or returns None if no match
    was found.
    Background: jail(8) doesn't allow dots in the name, they will be replaced
    with underscores. Because of this, foo.bar and foo_bar will be considered
    identical, as they cannot coexist.
    """
    uuid = uuid.replace(".", "_").replace("_", "[._]")
    matches = glob.glob(f"{iocroot}/jails/{uuid}") \
        + glob.glob(f"{iocroot}/templates/{uuid}")

    if old_uuid:
        try:
            matches.remove(old_uuid)
        except ValueError:
            pass

    if matches:
        return matches[0]
    else:
        return None


def consume_and_log(exec_gen, log=True, callback=None):
    """
    Consume a generator and massage the output with lines
    """
    output_list = []
    error_list = []
    stdout = stderr = ''

    def append_and_log(output):
        for i, v in enumerate(output):
            if v.endswith('\n'):
                a_list = error_list if i else output_list
                a_list.append(v)

                if log:
                    logit(
                        {
                            'level': 'INFO',
                            'message': v.rstrip()
                        },
                        _callback=callback
                    )

                output[i] = ''

        return output

    for output in filter(lambda o: any(v for v in o), exec_gen):
        output = list(output)
        if isinstance(output[0], bytes):
            for i in range(len(output)):
                output[i] = output[i].decode()

        o, e = output
        stdout += o
        stderr += e

        stdout, stderr = append_and_log([stdout, stderr])

    append_and_log([stdout, stderr])

    return {'stdout': output_list, 'stderr': error_list}


def get_jail_freebsd_version(path, release):
    """Checks the current patch level for the jail"""
    if release[:4].endswith('-'):
        # 9.3-RELEASE and under don't actually have this binary
        new_release = release
    else:
        with open(
            f'{path}/bin/freebsd-version', mode='r', encoding='utf-8'
        ) as r:
            for line in r:
                if line.startswith('USERLAND_VERSION'):
                    new_release = line.rstrip().partition('=')[
                        2].strip('"')

    return new_release


def truthy_values():
    return '1', 'on', 'yes', 'true', True, 1


def truthy_inverse_values():
    return '0', 'off', 'no', 'false', 0, False, None


def check_truthy(value):
    """Checks if the given value is 'True'"""
    if str(value).lower() in truthy_values():
        return 1

    return 0


def construct_truthy(item, inverse=False):
    """Will return an iterable with all truthy variations"""
    return (
        f'{item}={v}' for v in (
            truthy_inverse_values() if inverse else truthy_values()
        )
    )


def set_interactive(interactive):
    """Returns True or False if stdout is a tty"""
    global INTERACTIVE
    INTERACTIVE = interactive


def lowercase_set(values):
    return set([v.lower() for v in values])


def boolean_prop_exists(supplied_props, props_to_check):
    # supplied_props is a list i.e ["dhcp=1"]
    # props_to_check is a list of props i.e ["dhcp", "nat"]
    check_set = set()
    for check_prop in props_to_check:
        check_set.update(
            iocage_lib.ioc_common.lowercase_set(
                iocage_lib.ioc_common.construct_truthy(check_prop)
            )
        )

    return iocage_lib.ioc_common.lowercase_set(supplied_props) & check_set


def gen_unused_lo_ip():
    """Best effort to try to allocate a localhost IP for a jail"""
    interface_addrs = netifaces.ifaddresses('lo0')
    inuse = [ip['addr'] for ips in interface_addrs.values() for ip in ips
             if ip['addr'].startswith('127')]

    for ip in ipaddress.IPv4Network('127.0.0.0/8'):
        ip_exploded = ip.exploded

        if ip_exploded == '127.0.0.0':
            continue

        if ip_exploded not in inuse:
            return ip_exploded

    logit(
        {
            'level': 'EXCEPTION',
            'message': 'An unused RFC5735 compliant localhost address could'
            ' not be allocated.\nIf you wish to use a non-RFC5735 compliant'
            ' address, please manually set the localhost_ip property.'
        }
    )


def gen_nat_ip(ip_prefix):
    """Best effort to try to allocate a private NAT IP for a jail"""
    inuse = get_used_ips()

    for i in range(256):
        for l in range(1, 256, 4):
            network = ipaddress.IPv4Network(
                f'{ip_prefix}.{i}.{l}/30', strict=False
            )
            pair = [_ip.exploded for _ip in network.hosts()]

            if any(x in pair for x in inuse):
                continue

            return pair

    logit(
        {
            'level': 'EXCEPTION',
            'message': 'An unused RFC1918 compliant address could'
            ' not be allocated.\nPlease set an unused nat_prefix.'
        }
    )


def get_used_ips():
    """
    Run ifconfig in every jail and return an iteratable of the inuse addresses
    """
    jails = json.loads(
        su.run(
            ['jls', 'jid', '--libxo', 'json'], stdout=su.PIPE, stderr=su.PIPE
        ).stdout
    )['jail-information']['jail']
    addresses = []

    # Host
    inuse = su.run(
        ['ifconfig'], stdout=su.PIPE, stderr=su.PIPE, universal_newlines=True
    )
    for line in inuse.stdout.splitlines():
        if line.strip().startswith('inet'):
            address = line.split()[1]
            addresses.append(address)

    # Jails
    with concurrent.futures.ThreadPoolExecutor() as exc:
        futures = exc.map(
            lambda jail: su.run(
                ['jexec', jail['jid'], 'ifconfig'], stdout=su.PIPE,
                stderr=su.PIPE, universal_newlines=True
            ), jails
        )

        for future in futures:
            for line in future.stdout.splitlines():
                if line.strip().startswith('inet'):
                    address = line.split()[1]
                    addresses.append(address)

    return addresses


def parse_package_name(pkg):
    pkg, version = pkg.rsplit('-', 1)
    epoch_split = version.rsplit(',', 1)
    epoch = epoch_split[1] if len(epoch_split) == 2 else '0'
    revision_split = epoch_split[0].rsplit('_', 1)
    revision = \
        revision_split[1] if len(revision_split) == 2 else '0'
    revision = revision.replace(".txz", "")
    return {
        'version': revision_split[0],
        'revision': revision,
        'epoch': epoch,
    }


def get_host_gateways():
    gateways = {'ipv4': {'gateway': None, 'interface': None},
                'ipv6': {'gateway': None, 'interface': None}}
    af_mapping = {
        'Internet': 'ipv4',
        'Internet6': 'ipv6'
    }
    output = checkoutput(['netstat', '-r', '-n', '--libxo', 'json'])
    route_families = (json.loads(output)
                      ['statistics']
                      ['route-information']
                      ['route-table']
                      ['rt-family'])
    for af in af_mapping.keys():
        try:
            route_entries = list(filter(
                lambda x: x['address-family'] == af, route_families)
            )[0]['rt-entry']
        except IndexError:
            pass
        else:
            default_route = list(filter(
                lambda x: x['destination'] == 'default', route_entries)
            )
            if default_route and 'gateway' in default_route[0]:
                gateways[af_mapping[af]]['gateway'] = \
                    default_route[0]['gateway']
                gateways[af_mapping[af]]['interface'] = \
                    default_route[0]['interface-name']
    return gateways


def get_active_jails():
    return {
        d['name']: d for d in json.loads(
            checkoutput(['jls', '--libxo', 'json', '-v'])
        )['jail-information']['jail']
    }


def validate_plugin_manifest(manifest, _callback, silent):
    v = jsonschema.Draft7Validator(cache.plugin_manifest_schema)

    errors = []
    for e in v.iter_errors(manifest):
        errors.append(e.message)

    if errors:
        errors = '\n'.join(errors)
        logit(
            {
                'level': 'EXCEPTION',
                'message': f'The Following errors were encountered with plugin manifest:\n{errors}'
            },
            _callback=_callback,
            silent=silent,
        )


def retrieve_ip4_for_jail(conf, jail_running):
    short_ip4 = full_ip4 = None
    if iocage_lib.ioc_common.check_truthy(conf['dhcp']) and jail_running and os.geteuid() == 0:
        interface = conf['interfaces'].split(',')[0].split(':')[0]

        if interface == 'vnet0':
            # Inside jails they are epairNb
            interface = f"{interface.replace('vnet', 'epair')}b"

        short_ip4 = 'DHCP'
        full_ip4_cmd = [
            'jexec', f'ioc-{conf["host_hostuuid"].replace(".", "_")}',
            'ifconfig', interface, 'inet'
        ]
        try:
            out = su.check_output(full_ip4_cmd)
            full_ip4 = f'{interface}|{out.splitlines()[2].split()[1].decode()}'
        except (su.CalledProcessError, IndexError) as e:
            short_ip4 += '(Network Issue)'
            if isinstance(e, su.CalledProcessError):
                full_ip4 = f'DHCP - Network Issue: {e}'
            else:
                full_ip4 = f'DHCP - Failed Parsing: {e}'
    elif iocage_lib.ioc_common.check_truthy(conf['dhcp']) and not jail_running:
        short_ip4 = 'DHCP'
        full_ip4 = 'DHCP (not running)'
    elif iocage_lib.ioc_common.check_truthy(conf['dhcp']) and os.geteuid() != 0:
        short_ip4 = 'DHCP'
        full_ip4 = 'DHCP (running -- address requires root)'

    return {'short_ip4': short_ip4, 'full_ip4': full_ip4}


def retrieve_admin_portals(
    conf, jail_running, admin_portal, default_gateways=None, full_ipv4_dict=None
):
    # We want to ensure that we show the correct NAT ports for nat based plugins and when NAT
    # isn't desired, we don't show them at all. In all these variable values, what persists across
    # NAT/DHCP/Static ip based plugins is that the internal ports of the jail don't change. For
    # example if a plugin jail has nginx running on port 4000, it will still want to have it
    # running on 4000 regardless of the fact how user configures to start the plugin jail. We
    # take this fact, and search for an explicit specified port number in the admin portal, if
    # none is found, that means that it is ( 80 - default for http ).

    nat_forwards_dict = {}
    nat_forwards = conf.get('nat_forwards', 'none')
    for rule in nat_forwards.split(',') if nat_forwards != 'none' else ():
        # Rule can be proto(port), proto(in/out), port
        if rule.isdigit():
            jail = host = rule
        else:
            rule = rule.split('(')[-1].strip(')')
            if ':' in rule:
                jail, host = rule.split(':')
            else:
                # only one port provided
                jail = host = rule

        nat_forwards_dict[int(jail)] = int(host)

    if not conf.get('nat'):
        full_ipv4_dict = full_ipv4_dict or retrieve_ip4_for_jail(conf, jail_running)
        full_ip4 = full_ipv4_dict['full_ip4'] or conf.get('ip4_addr', '')
        all_ips = map(
            lambda v: 'DHCP' if 'dhcp' in v.lower() else v,
            [i.split('|')[-1].split('/')[0].strip() for i in full_ip4.split(',')]
        )
    else:
        default_gateways = default_gateways or iocage_lib.ioc_common.get_host_gateways()

        # We should list out the ips based on nat_interface property because that's the one which
        # the firewall will be handling port forwarding on TODO: pf/ipfw only do port forwarding
        # for the first ip address, we should update that so it works for all aliases. However
        # there doesn't seem to be a good way apart from hardcoding the ip aliases, we use the
        # dynamic option provided by the firewalls but that doesn't seem to take care of aliases,
        # only the first ip if it changes address - if we hardcode, that would mean applying
        # the firewall rules again on ip changes
        nat_iface = conf.get('nat_interface', 'none')
        all_ips = [
            f['addr'] for k in default_gateways if default_gateways[k]['interface']
            for f in netifaces.ifaddresses(
                default_gateways[k]['interface'] if nat_iface == 'none' else nat_iface
            )[netifaces.AF_INET if k == 'ipv4' else netifaces.AF_INET6]
        ] if nat_iface in netifaces.interfaces() or nat_iface == 'none' else []
        if all_ips:
            all_ips = [all_ips[0]]

    admin_portals = []
    for portal in admin_portal.split(','):
        if conf.get('nat'):
            portal_uri = urllib.parse.urlparse(portal)
            portal_port = portal_uri.port or 80
            # We do this safely as it's possible dev hasn't added it to plugin's json yet
            nat_port = nat_forwards_dict.get(portal_port)
            if nat_port:
                uri = portal_uri._replace(netloc=f'{portal_uri._hostinfo[0]}:{nat_port}').geturl()
            else:
                uri = portal
        else:
            uri = portal
        admin_portals.append(','.join(map(lambda v: uri.replace('%%IP%%', v), all_ips)))

    return admin_portals


def get_jails_with_config(filters=None, mapping_func=None):
    # FIXME: Due to how api is structured, there is no good place to put this
    #  so when we move on with restructuring the api, let's remove this as well
    #  importing iocage_lib.iocage above gives us a circular dep due to how
    #  iocage designates iocage_lib.iocage at top and imports everything else
    #  within.
    import iocage_lib.iocage
    return {
        j['host_hostuuid']: j if not mapping_func else mapping_func(j)
        for j in map(
            lambda v: list(v.values())[0],
            iocage_lib.iocage.IOCage(jail=None).get(
                'all', recursive=True
            )
        ) if not filters or filters(j)
    }


def tmp_dataset_checks(_callback, silent):
    tmp_dataset = Dataset('/tmp', cache=False)
    if tmp_dataset.exists:
        tmp_val = tmp_dataset.properties['exec']

        if tmp_val == 'off':
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{tmp_dataset.name} needs exec=on!'
                },
                _callback=_callback,
                silent=silent
            )
