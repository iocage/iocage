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
}


def log_callback(content, exception):
    print(content)
    print(exception)


def test_validate_plugin_manifest():
    validate_plugin_manifest(VALID_MANIFEST, log_callback, None)
