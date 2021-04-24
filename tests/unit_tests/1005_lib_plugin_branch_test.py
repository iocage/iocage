from unittest.mock import patch

from iocage_lib.ioc_plugin import IOCPlugin

test_branch = "TEST_BRANCH"


@patch("iocage_lib.ioc_json.IOCJson")
def test_set_plugin_branch(mocked_ioc_json):
    plugin = IOCPlugin(branch=test_branch)

    assert plugin.index_branch == test_branch
    assert plugin.__get_plugin_branch__({}) == test_branch
