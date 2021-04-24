from unittest.mock import patch, PropertyMock

from iocage_lib.ioc_plugin import IOCPlugin


@patch("iocage_lib.ioc_json.IOCJson")
@patch("iocage_lib.cache.Cache.freebsd_version", new_callable=PropertyMock)
def test_default_branch_values(mocked_cache, mocked_ioc_json):
    mocked_cache.return_value = "12.2"

    plugin = IOCPlugin()

    assert plugin.index_branch == "12.2-RELEASE"
    assert plugin.__get_plugin_branch__({}) == "master"


@patch("iocage_lib.ioc_json.IOCJson")
def test_set_plugin_branch(mocked_ioc_json):
    test_branch = "TEST_BRANCH"
    plugin = IOCPlugin(branch=test_branch)

    assert plugin.index_branch == test_branch
    assert plugin.__get_plugin_branch__({}) == test_branch


@patch("iocage_lib.ioc_json.IOCJson")
@patch("iocage_lib.cache.Cache.freebsd_version", new_callable=PropertyMock)
def test_plugin_manifest_branch(mocked_cache, mocked_ioc_json):
    mocked_cache.return_value = "12.2"
    plugin_branch = "plugin_branch"
    plugin_manifest = {"branch": plugin_branch}

    plugin = IOCPlugin()

    assert plugin.index_branch == "12.2-RELEASE"
    assert plugin.__get_plugin_branch__(plugin_manifest) == plugin_branch


@patch("iocage_lib.ioc_json.IOCJson")
@patch("iocage_lib.cache.Cache.freebsd_version", new_callable=PropertyMock)
def test_hardened_plugin(mocked_cache, mocked_ioc_json):
    mocked_cache.return_value = "12.2"

    plugin = IOCPlugin(hardened=True)

    assert plugin.index_branch == "master"
    assert plugin.__get_plugin_branch__({}) == "master"
