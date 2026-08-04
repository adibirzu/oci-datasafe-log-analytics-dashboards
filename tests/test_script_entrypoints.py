"""Direct operator scripts must not depend on a caller-set PYTHONPATH."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "script",
    [
        "discover.py",
        "e2e.py",
        "setup_log_analytics_content.py",
        "export_log_analytics_content.py",
    ],
)
def test_operator_script_help_runs_without_pythonpath(script):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(  # noqa: S603
        [sys.executable, f"scripts/{script}", "--help"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_discovery_safe_main_redacts_oci_service_metadata(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("discover", ROOT / "scripts" / "discover.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def fail():
        raise module.oci.exceptions.ServiceError(
            status=400,
            code="InvalidParameter",
            headers={},
            message="tenant-specific message must not be printed",
        )

    monkeypatch.setattr(module, "main", fail)
    assert module.safe_main() == 2
    assert "tenant-specific" not in capsys.readouterr().out


def test_discovery_source_does_not_include_profile_or_region_in_reports():
    source = (ROOT / "scripts" / "discover.py").read_text()
    assert '"profile": profile' not in source
    assert '"region": config["region"]' not in source
