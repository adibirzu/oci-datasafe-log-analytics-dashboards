import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "deploy_all", ROOT / "scripts" / "deploy_all.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_apply_invokes_new_function_and_requires_export(monkeypatch, tmp_path):
    tfvars = tmp_path / "terraform.tfvars"
    tfvars.write_text("deployment_name = \"example\"\n")
    commands = []

    def fake_run(command, *, capture=False):
        commands.append(command)
        if command[:4] == ["terraform", "-chdir=terraform", "show", "-json"]:
            return SimpleNamespace(stdout='{"resource_changes": []}')
        if command == [
            "terraform",
            "-chdir=terraform",
            "output",
            "-raw",
            "function_id",
        ]:
            return SimpleNamespace(stdout="ocid1.fnfunc.oc1..example")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(MODULE, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy_all.py",
            "--profile",
            "customer-profile",
            "--data-safe-compartment-id",
            "customer-data-safe-compartment",
            "--solution-compartment-id",
            "customer-solution-compartment",
            "--deployment-name",
            "customer-deployment",
            "--tfvars",
            str(tfvars),
            "--apply",
        ],
    )

    assert MODULE.main() == 0
    e2e = next(command for command in commands if "scripts/e2e.py" in command)
    assert "--invoke-function-id" in e2e
    assert "ocid1.fnfunc.oc1..example" in e2e
    assert "--require-function-export" in e2e
