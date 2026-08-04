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
            ".terraform/" in name or name.endswith((".tfstate", ".plan")) for name in names
        )


def test_logging_connector_leaves_stream_only_source_identifier_unset():
    main = (ROOT / "terraform" / "main.tf").read_text()
    assert "log_source_identifier" not in main


def test_portable_content_maps_the_current_export_marker_without_tenant_data():
    content_zip = ROOT / "terraform" / "content" / "oci-datasafe-log-analytics-content.zip"
    with zipfile.ZipFile(content_zip) as archive:
        content = archive.read("content.xml")
    assert b"<DisplayName>Export Run ID</DisplayName>" in content
    assert b"<StructuredColInfo>$.data.export_run_id</StructuredColInfo>" in content
    assert b"ocid1." not in content


def test_readme_deploy_button_targets_the_published_resource_manager_archive():
    readme = (ROOT / "README.md").read_text()
    assert "Deploy to Oracle Cloud" in readme
    assert "releases/latest/download/oci-datasafe-log-analytics-stack.zip" in readme


def test_function_image_contract_requires_a_unique_tag_not_a_digest():
    variables = (ROOT / "terraform" / "variables.tf").read_text()
    main = (ROOT / "terraform" / "main.tf").read_text()
    assert "does not accept a digest reference" in variables
    assert "OCI Functions does not accept a digest reference" in main
