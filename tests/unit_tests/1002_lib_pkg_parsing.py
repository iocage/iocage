from iocage_lib.ioc_common import parse_package_name


# Tests for point 1
def test_01_version_check():
    assert parse_package_name('ImageMagick7-7.0.8.47')['version'] == '7.0.8.47'
    assert parse_package_name('ImageMagick7-7.0.8.47')['revision'] == '0'


def test_02_revision():
    assert parse_package_name('ORBit2-2.14.19_2.txz')['revision'] == '2'


def test_03_epoch():
    assert parse_package_name('ap24-mod_perl2-2.0.10,3')['epoch'] == '3'


def test_04_version_revision_epoch():
    data = parse_package_name('dnsmasq-2.80_2,1')
    assert data['version'] == '2.80'
    assert data['revision'] == '2'
    assert data['epoch'] == '0'
