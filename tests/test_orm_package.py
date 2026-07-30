import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_orm_package", ROOT / "scripts" / "build_orm_package.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_resource_manager_package_is_rooted_and_secret_free(tmp_path):
    output = tmp_path / "stack.zip"
    first = MODULE.build(output)
    second = MODULE.build(output)
    assert first == second
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert {"main.tf", "schema.yaml", "dashboard_bundle.json"} <= names
        assert "content/oci-datasafe-log-analytics-content.zip" in names
        assert not any(
            ".terraform/" in name or name.endswith((".tfstate", ".plan"))
            for name in names
        )


def test_logging_connector_leaves_stream_only_source_identifier_unset():
    main = (ROOT / "terraform" / "main.tf").read_text()
    assert "log_source_identifier" not in main
