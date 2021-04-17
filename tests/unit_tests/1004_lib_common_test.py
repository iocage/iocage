import pytest

from iocage_lib.ioc_common import validate_plugin_manifest

VALID_MANIFEST = {
    "name": "test_plugin",
    "release": "12.2-RELEASE",
    "pkgs": [],
    "packagesite": "http://pkg.FreeBSD.org/${ABI}/latest",
    "fingerprints": {
        "iocage-plugins": [
            {
                "function": "sha256",
                "fingerprint": "b0170035af3acc5f3f3ae1859dc717101b4e6c1d0a794ad554928ca0cbb2f438"
            }
        ]
    },
    "artifact": "TEST_ARTIFACT",
}


def test_validate_plugin_manifest():
    validate_plugin_manifest(VALID_MANIFEST, None, None)


@pytest.mark.parametrize(
    "missing_field",
    ["name", "release", "pkgs", "packagesite", "fingerprints", "artifact"]
)
def test_missing_required_fields(missing_field):
    manifest = VALID_MANIFEST.copy()
    del manifest[missing_field]

    exp_msg = f"Missing \"{missing_field}\" key in manifest"
    with pytest.raises(RuntimeError, match=exp_msg):
        validate_plugin_manifest(manifest, None, None)
