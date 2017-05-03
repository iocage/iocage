import re

import pytest
from click.testing import CliRunner

from iocage import main as ioc

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_fetch(release, server, user, password, auth, root_dir, http, _file,
               noupdate, hardened):
    if hardened:
        release = release.replace("-RELEASE", "-STABLE")
        release = re.sub(r"\W\w.", "-", release)

    # Type Errors are bad mmmkay
    command = ["fetch", "-r", release]
    command += ["-s", server] if server else []
    command += ["-h"] if http else []
    command += ["-f", _file] if _file else []
    command += ["-u", user] if user else []
    command += ["-p", password] if password else []
    command += ["-a", auth] if auth else []
    command += ["-d", root_dir] if root_dir else []
    command += ["-NU"] if noupdate else []

    runner = CliRunner()
    result = runner.invoke(ioc.cli, command)

    assert result.exit_code == 0
