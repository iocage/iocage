from unittest.mock import patch, PropertyMock

from iocage_lib.ioc_plugin import IOCPlugin

test_branch = "TEST_BRANCH"


@patch("iocage_lib.ioc_json.IOCJson")
def test_set_plugin_branch(mocked_ioc_json):
    plugin = IOCPlugin(branch=test_branch)

    assert plugin.index_branch == test_branch
    assert plugin.__get_plugin_branch__({}) == test_branch


@patch("iocage_lib.ioc_json.IOCJson")
@patch("iocage_lib.cache.Cache.freebsd_version", new_callable=PropertyMock)
def test_default_branch_values(mocked_cache, mocked_ioc_json):
    mocked_cache.return_value = "12.2"

    plugin = IOCPlugin()

    assert plugin.index_branch == "12.2-RELEASE"
    assert plugin.__get_plugin_branch__({}) == "master"



