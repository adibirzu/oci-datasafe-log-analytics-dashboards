import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "setup_log_analytics_content",
    ROOT / "scripts" / "setup_log_analytics_content.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_custom_source_identifier_matches_function_cloud_event_type():
    exporter = (ROOT / "src" / "oci_datasafe_exporter" / "exporter.py").read_text()
    assert MODULE.SOURCE_INTERNAL == "com.oraclecloud.logging.custom.datasafe.audit"
    assert f'type="{MODULE.SOURCE_INTERNAL}"' in exporter


def test_parser_example_and_paths_include_oci_logging_wrapper():
    assert MODULE.EXAMPLE["data"]["schema_version"] == "2.0"
    assert MODULE.EXAMPLE["type"] == MODULE.SOURCE_INTERNAL
    assert MODULE.EXAMPLE["data"] is MODULE.EVENT_EXAMPLE
