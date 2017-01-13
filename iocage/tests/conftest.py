import pytest


def pytest_addoption(parser):
    parser.addoption("--zpool", action="store", default=None,
                     help="Specify a zpool to use.")
    parser.addoption("--release", action="store", default="11.0-RELEASE",
                     help="Specify a RELEASE to use.")
    parser.addoption("--server", action="store", default="ftp.freebsd.org",
                     help="FTP server to login to.")
    parser.addoption("--user", action="store", default="anonymous",
                     help="The user to use.")
    parser.addoption("--password", action="store", default="anonymous@",
                     help="The password to use.")
    parser.addoption("--http", action="store_true",
                     help="Have --server define a HTTP server instead.")
    parser.addoption("--auth", action="store", default=None,
                     help="Authentication method "
                          "for "
                          "HTTP fetching. Valid "
                          "values: basic, digest")

    parser.addoption("--file", action="store_true",
                     help="Use a local file directory for root-dir instead of "
                          "FTP or HTTP.")
    parser.addoption(
            "--root-dir", action="store",
            help="Root directory containing all the RELEASEs.")


@pytest.fixture
def zpool(request):
    return request.config.getoption("--zpool")


@pytest.fixture
def release(request):
    return request.config.getoption("--release")


@pytest.fixture
def server(request):
    return request.config.getoption("--server")


@pytest.fixture
def user(request):
    return request.config.getoption("--user")


@pytest.fixture
def password(request):
    return request.config.getoption("--password")


@pytest.fixture
def root_dir(request):
    return request.config.getoption("--root-dir")


@pytest.fixture
def http(request):
    return request.config.getoption("--http")


@pytest.fixture
def _file(request):
    return request.config.getoption("--file")


@pytest.fixture
def auth(request):
    return request.config.getoption("--auth")
