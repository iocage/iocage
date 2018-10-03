# Copyright (c) 2014-2018, iocage
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
import sys
import tempfile as tmp
import requests
import datetime as dt
import re
import shlex
import glob


def callback(_log, callback_exception):
    """Helper to call the appropriate logging level"""
    log = logging.getLogger("iocage")
    level = _log["level"]
    message = _log["message"]
    force_raise = _log.get("force_raise")

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
        try:
            if not os.isatty(sys.stdout.fileno()):
                raise callback_exception(message)
            else:
                log.error(message)
                if force_raise:
                    raise callback_exception(message)
                else:
                    raise SystemExit(1)
        except AttributeError:
            # They are lacking the fileno object
            raise callback_exception(message)


def logit(content, _callback=None, silent=False, exception=RuntimeError):
    """Helper to check callable status of callback or call ours."""
    if silent and content['level'] != "EXCEPTION":
        # They need to see these errors, too bad!
        return

    # This will log with our callback method if they didn't supply one.
    _callback = _callback if callable(_callback) else callback
    _callback(content, exception)


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
        "used": sort_qta
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


def sort_ip(ip, version="4"):
    """Sort the list by IP address."""
    list_length = len(ip)

    # Length 9 is list -l, 10 is list -P
    # Length 5 is list

    if list_length == 9 or list_length == 10:
        try:
            _ip = ip[6] if version == "4" else ip[7]
            _ip = str(ipaddress.ip_address(_ip.rsplit("|")[1].split("/")[0]))
            if version == "4":
                _ip = tuple(int(c) for c in _ip.split("."))
            else:
                _ip = (0,) + tuple(c for c in _ip.split(":"))

        except (ValueError, IndexError):
            # Lame hack to have "-" or invalid/undetermined IPs last.
            _ip = 300, _ip

        # Tack on the NAME as secondary sort criterion
        _ip = _ip + get_name_sortkey(ip[1])

    elif list_length == 5:
        try:
            _ip = str(ipaddress.ip_address(ip[4]))
            _ip = tuple(int(c) for c in _ip.split("."))

        except ValueError:
            # Lame hack to have "-" or invalid/undetermined IPs last.
            _ip = 300, ip[4]

        # Tack on the NAME as as secondary sort criterion
        _ip = _ip + get_name_sortkey(ip[1])

    else:
        _ip = ip

    return _ip


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
    _boot = 0 if boot[2] != "off" else 1
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


def sort_template(template):
    """Helper function for templates to be sorted in sort_name"""
    # Ugly hack to have templates listed first, this assumes they will not
    # name their template with this string, it would be *remarkable* if they
    # did.
    _template = template[8] if template[8] != "-" else "z" * 999999

    return sort_name(_template) + get_name_sortkey(template[1])


def sort_release(releases, split=False):
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

        if length == 9 or length == 10:
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
        for rel in releases:
            rel, r_type = rel.properties["mountpoint"].value.rsplit("/")[
                -1].split("-", 1)

            if len(rel) > 2:
                rel = float(rel)

            r_dict[rel] = r_type
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
            release_list.insert(index, [f"{r}-{t}"])
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

        out = out.decode("utf-8")
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


def check_release_newer(release, callback=None, silent=False):
    """Checks if the host RELEASE is greater than the target release"""
    host_release = get_host_release()

    if host_release == "Not a RELEASE":
        return

    h_float = float(str(host_release).rsplit("-", 1)[0])
    r_float = float(str(release).rsplit("-", 1)[0])

    if h_float < r_float:
        logit(
            {
                "level": "EXCEPTION",
                "message": f"\nHost: {host_release} is not greater"
                f" than target: {release}\nThis is unsupported."
            },
            _callback=callback,
            silent=silent)


def construct_devfs(ruleset_name, paths, includes=None, comment=None):
    """
    ruleset_name: The ruleset without the brackets or a number,
        for example 'foo' will be contructed into [foo=IOCAGE_GEN_RULENUM]

    Will construct a devfs ruleset from dict(paths), and list(includes) with:
        paths dict:
            EXAMPLE: "usbctl": mode 660 group uucp
            - path to unhide: mode (can be None)
        includes list:
            EXAMPLE ["$devfsrules_hide_all", "$devfsrules_unhide_basic"]
            - [entry, entry]

    Returns a tuple containing the string and which devfs_ruleset got assigned.
    """
    includes = [] if includes is None else includes
    ct_str = f'## {ruleset_name}' if comment is None else comment
    rules = []
    ruleset_number = 5  # The system has 4 already claimed.

    try:
        with open('/etc/devfs.rules', 'r') as f:
            exists = False

            for line in f.readlines():
                if line.rstrip() == ct_str:
                    exists = True
                    continue

                if exists:
                    return None, int(line.rsplit('=')[1].strip(']\n'))

                if line.startswith('['):
                    try:
                        line = int(line.rsplit('=')[1].strip(']\n'))
                    except IndexError:
                        rules.append(line)
                    rules.append(line)
    except FileNotFoundError:
        logit(
            {
                'level': 'EXCEPTION',
                'message':
                    '/etc/devfs.rules could not be found, unable to continue.'
            }
        )

    while ruleset_number in rules:
        ruleset_number += 1

    devfs_string = f'\n{ct_str}\n[{ruleset_name}={ruleset_number}]'

    for include in includes:
        devfs_string += f'\nadd include {include}'

    for path, mode in paths.items():
        path_str = f'add path \'{path}\''

        if mode is not None:
            path_str += f' {mode}'
        else:
            path_str += ' unhide'

        devfs_string += f'\n{path_str}'

    return f'{devfs_string}\n', str(ruleset_number)


def runscript(script):
    """
    Runs the users provided script, otherwise returns a tuple with
    True/False and the error.
    """
    script = shlex.split(script)

    if len(script) > 1:
        # We may be getting ';', '&&' and so forth. Adding the shell for
        # safety.
        script = ["/bin/sh", "-c", " ".join(script)]
    elif os.access(script[0], os.X_OK):
        script = script[0]
    else:
        return True, "Script is not executable!"

    try:
        out = checkoutput(script, stderr=su.STDOUT)
    except su.CalledProcessError as err:
        return False, err.output.decode().rstrip("\n")

    if out:
        return True, out.rstrip("\n")

    return True, None


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
