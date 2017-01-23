"""Common methods we reuse."""
import shutil

import os
import stat


def sort_tag(tag):
    """Sort the list by tag."""
    list_length = len(tag)

    # Length 8 is list -l, 7 is df, 5 is list
    if list_length == 8:
        _tag = tag[4]
    elif list_length == 7:
        _tag = tag[6]
    elif list_length == 5:
        _tag = tag[3]
    else:
        _tag = tag[1]

    _sort = _tag.rsplit('_', 1)

    # We want to sort tags that have been created with count > 1. But not
    # foo_bar
    if len(_sort) > 1 and _sort[1].isdigit():
        return _sort[0], int(_sort[1])
    else:
        return _tag, 0


def sort_release(releases, iocroot, split=False):
    """
    Sort the list by RELEASE, if split is true it's expecting full
    datasets.
    """
    release_list = []

    if split:
        for rel in releases:
            rel = float(rel.split(iocroot)[1].split("/")[2].split("-")[0])

            release_list.append(rel)
    else:
        for release in releases:
            if "-RELEASE" in release:
                release = float(release.split("-")[0])
                release_list.append(release)

    release_list.sort()

    for r in release_list:
        index = release_list.index(r)
        release_list.remove(r)

        if split:
            # We want these sorted, so we cheat a bit.
            release_list.insert(index, ["{}-RELEASE".format(r)])
        else:
            # We want these sorted, so we cheat a bit.
            release_list.insert(index, "{}-RELEASE".format(r))

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
