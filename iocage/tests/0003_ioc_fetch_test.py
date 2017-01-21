from iocage.lib.ioc_fetch import IOCFetch


def test_fetch(http, _file, server, user, password, auth, release, root_dir):
    IOCFetch(release, server, user, password, auth, root_dir, http=http,
             _file=_file).fetch_release()

    assert True == True
