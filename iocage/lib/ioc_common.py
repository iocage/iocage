"""Common methods we reuse."""
import collections
import os
import shutil
import stat
import tempfile as tmp
from contextlib import contextmanager

from future.backports import check_output


def sort_tag(tag):
    """Sort the list by tag."""
    list_length = len(tag)

    # Length 8 is list -l, 7 is df, 5 is list
    if list_length == 9:
        _tag = tag[4]
    elif list_length == 7:
        _tag = tag[6]
    elif list_length == 6:
        _tag = tag[3]
    else:
        _tag = tag[1]

    _sort = _tag.rsplit('_', 1)

    # We want to sort tags that have been created with count > 1. But not
    # foo_bar
    if len(_sort) > 1 and _sort[1].isdigit():
        return _sort[0], int(_sort[1])
    else:
        return _tag, 1


def sort_release(releases, iocroot, split=False):
    """
    Sort the list by RELEASE, if split is true it's expecting full
    datasets.
    """
    r_dict = {}
    release_list = []

    if split:
        for rel in releases:
            rel, r_type = rel.split(iocroot)[1].split("/")[2].split("-")

            if len(rel) > 2:
                rel = float(rel)

            r_dict[rel] = r_type
    else:
        for release in releases:
            try:
                release, r_type = release.split("-")

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
@contextmanager
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


@contextmanager
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


def indent_lines(message):
    """This will indent all lines except the first by 7 spaces. """
    indented = message.replace("\n", "\n       ").rstrip()

    return indented


def get_nested_key(_dict, keys=[]):
    """Gets a nested key from a dictionary."""
    key = keys.pop(0)

    if len(keys) == 0:
        return _dict[key]

    return get_nested_key(_dict[key], keys)


def checkoutput(*args, **kwargs):
    """Just a wrapper to return utf-8 from check_output"""
    out = check_output(*args, **kwargs).decode("utf-8")

    return out
