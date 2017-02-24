import mock
import pytest
from iocage.cli.activate import\
    (get_zfs_pools, set_zfs_pool_active_property, set_zfs_pool_comment)


@mock.patch('iocage.cli.activate.Popen.communicate')
def test_get_zfs_pools_multiple_pools(mock_communicate):
    """ Fake the expected output from zpool list -H -o name
        on a system with 3 ZFS pools
    """
    mock_communicate.return_value = (b'tank0\ntank1\ntank2\n', None)

    zpools = get_zfs_pools()
    mock_communicate.assert_called()

    assert zpools == ['tank0', 'tank1', 'tank2']


@mock.patch('iocage.cli.activate.Popen.communicate')
def test_get_zfs_pools_one_pool(mock_communicate):
    """ Fake the expected output from zpool list -H -o name
        on a system with 1 ZFS pool
     """
    mock_communicate.return_value = (b'tank0\n', None)

    zpools = get_zfs_pools()
    mock_communicate.assert_called()

    assert zpools == ['tank0']


@mock.patch('iocage.cli.activate.Popen.communicate')
def test_get_zfs_pools_no_pool(mock_communicate):
    """ Fake the expected output from zpool list -H -o name
        on a system with zero ZFS pool
     """
    mock_communicate.return_value = (b'', None)

    zpools = get_zfs_pools()
    mock_communicate.assert_called()

    assert zpools == []


@mock.patch('iocage.cli.activate.Popen.communicate')
def test_get_zfs_pools_bad_parameter(mock_communicate):
    """ Fake zpool called with an incorrect parameter
    (there is something in stderr), can save us when
    updating the code
     """
    mock_communicate.return_value = (b'',
                                     b"""cannot open 'nope-parameter': no such pool\ncannot open '-o':
                                     name must begin with a letter\ncannot open 'name': no such pool\n""")

    with pytest.raises(RuntimeError):
        zpools = get_zfs_pools()
        mock_communicate.assert_called()


def test_set_zfs_pool_active_property_bad_param_zpool_name():
    with pytest.raises(ValueError):
        set_zfs_pool_active_property(None, True)

    with pytest.raises(ValueError):
        set_zfs_pool_active_property("", True)

    with pytest.raises(ValueError):
        set_zfs_pool_active_property(1, True)

    with pytest.raises(ValueError):
        set_zfs_pool_active_property([], True)


def test_set_zfs_pool_active_property_bad_param_activate():
    with pytest.raises(ValueError):
        set_zfs_pool_active_property("pool_name", None)

    with pytest.raises(ValueError):
        set_zfs_pool_active_property("pool_name", [])

    with pytest.raises(ValueError):
        set_zfs_pool_active_property("pool_name", 1)


@mock.patch('iocage.cli.activate.Popen.communicate')
def test_set_zfs_pool_active_property_ok(mock_communicate):
    mock_communicate.return_value = (b'', b'')
    set_zfs_pool_active_property("pool_name", True)
    assert mock_communicate.called


@mock.patch('iocage.cli.activate.Popen.communicate')
def test_set_zfs_pool_active_property_fail(mock_communicate):
    mock_communicate.return_value = (b'', b"cannot set property for 'tank0': invalid property 'foo'\n")
    with pytest.raises(RuntimeError):
        set_zfs_pool_active_property("pool_name", True)

    with pytest.raises(RuntimeError):
        set_zfs_pool_active_property("pool_name", False)


def test_set_zfs_pool_comment_bad_param ():
    with pytest.raises(ValueError):
        set_zfs_pool_comment(None, "comment")

    with pytest.raises(ValueError):
        set_zfs_pool_comment("", "comment")

    with pytest.raises(ValueError):
        set_zfs_pool_comment("pool", None)

    with pytest.raises(ValueError):
        set_zfs_pool_comment("pool", "")


@mock.patch('iocage.cli.activate.Popen.communicate')
def test_set_zfs_pool_comment_fail(mock_communicate):
    mock_communicate.return_value = (b'', b"cannot set property for 'tank0': permission denied\n")
    with pytest.raises(RuntimeError):
        set_zfs_pool_comment("pool", "comment")