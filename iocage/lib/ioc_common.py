# Copyright (c) 2014-2017, iocage
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
import os
import shutil
import stat
import subprocess as su
import sys
import tempfile as tmp

import pygit2

import iocage.lib.ioc_logger


def callback(log):
    """Helper to call the appropriate logging level"""
    lgr = iocage.lib.ioc_logger.IOCLogger().cli_log()

    if log['level'] == 'CRITICAL':
        lgr.critical(log['message'])
    elif log['level'] == 'ERROR':
        lgr.error(log['message'])
    elif log['level'] == 'WARNING':
        lgr.warning(log['message'])
    elif log['level'] == 'INFO':
        lgr.info(log['message'])
    elif log['level'] == 'DEBUG':
        lgr.debug(log['message'])
    elif log['level'] == 'VERBOSE':
        lgr.verbose(log['message'])
    elif log['level'] == 'NOTICE':
        lgr.notice(log['message'])
    elif log['level'] == 'EXCEPTION':
        # TODO: Better solution?
        if not os.isatty(sys.stdout.fileno()):
            raise RuntimeError(log['message'])
        else:
            lgr.error(log['message'])
            raise SystemExit(log['message'])


def logit(content, _callback=None, silent=False):
    """Helper to check callable status of callback or call ours."""
    level = content["level"]
    msg = content["message"]

    if silent:
        if level != "EXCEPTION":
            # They need to see these errors, too bad!
            return

    if callable(_callback):
        _callback({"level": level, "message": msg})
    else:
        # This will log with our callback method if they didn't supply one.
        callback(content)


def raise_sort_error(sort_list):
    msg = "Invalid sort type specified, use one of:\n"

    for s in sort_list:
        msg += f"  {s}\n"

    logit({
        "level"  : "ERROR",
        "message": msg.rstrip()
    })

    raise RuntimeError()


def ioc_sort(caller, s_type, data=None):
    try:
        s_type = s_type.lower()
    except AttributeError:
        # When a failed template is attempted, it will set s_type to None.
        s_type = "tag"

    sort_funcs = {
        "jid"     : sort_jid,
        "uuid"    : sort_uuid,
        "boot"    : sort_boot,
        "state"   : sort_state,
        "tag"     : sort_tag,
        "type"    : sort_type,
        "release" : sort_release,
        "ip4"     : sort_ip,
        "ip6"     : sort_ip6,
        "template": sort_template,
        "crt"     : sort_crt,
        "res"     : sort_res,
        "qta"     : sort_qta,
        "use"     : sort_use,
        "ava"     : sort_ava
    }

    list_full_sorts = ["jid", "uuid", "boot", "state", "tag", "type",
                       "release", "ip4", "ip6", "template"]
    list_short_sorts = ["jid", "uuid", "state", "tag", "release", "ip4"]
    df_sorts = ["uuid", "crt", "res", "qta", "use", "ava", "tag"]

    if caller == "list_full" and s_type not in list_full_sorts:
        raise_sort_error(list_full_sorts)
    elif caller == "list_short" and s_type not in list_short_sorts:
        raise_sort_error(list_short_sorts)
    elif caller == "df" and s_type not in df_sorts:
        raise_sort_error(df_sorts)

    # Most calls will use this
    if caller == "list_release" and s_type == "release":
        return sort_release(data, split=True)

    return sort_funcs.get(s_type)


def sort_crt(crt):
    """Sort df by CRT"""
    return crt[1]


def sort_res(res):
    """Sort df by RES"""
    return res[2]


def sort_qta(qta):
    """Sort df by QTA"""
    return qta[3]


def sort_use(use):
    """Sort df by USE"""
    return use[4]


def sort_ava(ava):
    """Sort df by AVA"""
    return ava[5]


def sort_ip6(ip):
    """Helper for sort_ip"""
    return sort_ip(ip, version="6")


def sort_ip(ip, version="4"):
    """Sort the list by IP address."""
    list_length = len(ip)

    # Length 10 is list -l, 5 is list
    if list_length == 10:
        try:
            ip = ip[7] if version == "4" else ip[8]
            _ip = str(ipaddress.ip_address(ip.rsplit("|")[1]))
        except (ValueError, IndexError):
            # Lame hack to have "-" last.
            _ip = "Z"
    elif list_length == 6:
        try:
            _ip = str(ipaddress.ip_address(ip[5]))
        except ValueError:
            # Lame hack to have "-" last.
            _ip = "Z"
    else:
        _ip = ip

    return _ip


def sort_type(jail_type):
    """Sort the list by jail type."""
    return jail_type[5]


def sort_state(state):
    """Sort the list by state."""
    list_length = len(state)

    # Length 10 is list -l, 5 is list
    if list_length == 10:
        _state = 0 if state[3] != "down" else 1
    elif list_length == 6:
        _state = 0 if state[2] != "down" else 1
    else:
        _state = state

    # 0 is up, 1 is down, lame hack to get running jails on top.
    return _state


def sort_boot(boot):
    """Sort the list by boot."""
    # Lame hack to get on above off.
    return 0 if boot[2] != "off" else 1


def sort_jid(jid):
    """Sort the list by JID."""
    # Lame hack to have jails not runnig below running jails.
    return jid[0] if jid[0] != "-" else "a"


def sort_uuid(uuid):
    """Sort the list by UUID."""
    list_length = len(uuid)

    return uuid[1] if list_length != 7 else uuid[0]


def sort_template(template):
    """Helper function for templates to be sorted in sort_name"""
    # Ugly hack to have templates listed first, this assumes they will not
    # name their template with this string, it would be *remarkable* if they
    # did.
    _template = template[9] if template[9] != "-" else "z" * 999999

    return sort_name(_template)


def sort_tag(tag):
    """Helper function for tags to be sorted in sort_name"""
    # Length 10 is list -l, 7 is df, 6 is list
    list_length = len(tag)

    if list_length == 10:
        _tag = tag[4]
    elif list_length == 7:
        _tag = tag[6]
    elif list_length == 6:
        _tag = tag[3]
    else:
        _tag = tag[1]

    return sort_name(_tag)


def sort_name(name):
    """Sort the list by name."""
    _sort = name.rsplit('_', 1)

    # We want to sort names that have been created with count > 1. But not
    # foo_bar
    if len(_sort) > 1 and _sort[1].isdigit():
        return _sort[0], int(_sort[1])
    else:
        return name, 0


def sort_release(releases, split=False):
    """
    Sort the list by RELEASE, if split is true it's expecting full
    datasets.
    """
    r_dict = {}
    release_list = []
    list_sort = False

    try:
        length = len(releases)

        if length == 10:
            # We don't want the -p* stuff.
            releases = releases[6].rsplit("-", 1)[0]
            list_sort = True
        elif length == 6:
            releases = releases[4]
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
            if len(releases.split(".")[0]) < 2:
                releases = f"0{releases}"

            return releases
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
            release_list.insert(index, ["{}-{}".format(r, t)])
            index += 1
        else:
            release_list.insert(index, "{}-{}".format(r, t))
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
            except:
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


def git_pull(repo, remote_name="origin", branch="master"):
    """Method that will replicate a git pull."""
    # Adapted from:
    # @formatter:off
    # https://raw.githubusercontent.com/MichaelBoselowitz/pygit2-examples/master/examples.py
    # @formatter:on
    for remote in repo.remotes:
        if remote.name == remote_name:
            remote.fetch()
            remote_master_id = repo.lookup_reference(
                f"refs/remotes/origin/{branch}").target
            merge_result, _ = repo.merge_analysis(remote_master_id)
            # Up to date, do nothing
            if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                return
            # We can just fastforward
            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                repo.checkout_tree(repo.get(remote_master_id))
                try:
                    master_ref = repo.lookup_reference(f'refs/heads/{branch}')
                    master_ref.set_target(remote_master_id)
                except KeyError:
                    repo.create_branch(branch, repo.get(remote_master_id))
                repo.head.set_target(remote_master_id)
            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                repo.merge(remote_master_id)

                if repo.index.conflicts is not None:
                    for conflict in repo.index.conflicts:
                        logit({
                            "level"  : "EXCEPTION",
                            "message": "Conflicts found in:"
                                       f" {conflict[0].path}"
                        })

                user = repo.default_signature
                tree = repo.index.write_tree()
                repo.create_commit('HEAD', user, user, "merged by iocage",
                                   tree, [repo.head.target, remote_master_id])
                # We need to do this or git CLI will think we are still
                # merging.
                repo.state_cleanup()
            else:
                raise AssertionError("Unknown merge analysis result")


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
