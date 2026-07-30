import json
from pathlib import Path

from oci_datasafe_exporter.config import ExportConfig
from oci_datasafe_exporter.normalize import normalize_event

FIXTURE = Path(__file__).parent / "fixtures" / "audit_event.json"


def config(**overrides):
    values = dict(
        data_safe_compartment_id="compartment",
        logging_log_id="log",
        cursor_bucket_name="bucket",
        client_ip_hash_salt="a-secure-test-salt",
    )
    values.update(overrides)
    return ExportConfig(**values)


def test_normalization_is_privacy_aware_and_dashboard_ready():
    event = normalize_event(json.loads(FIXTURE.read_text()), config())
    assert event["id"] == "event-001"
    assert event["db_user_name"] == "APP_USER"
    assert event["client_ip"].startswith("ip-")
    assert event["client_ip"] != "10.0.0.10"
    assert "command_text" not in event
    assert "command_param" not in event


def test_sql_text_requires_explicit_opt_in():
    event = normalize_event(
        json.loads(FIXTURE.read_text()),
        config(include_sql_text=True, include_command_parameters=True),
    )
    assert event["command_text"].startswith("select")
    assert event["command_param"] == "token=secret"


def test_normalization_preserves_the_complete_audit_event_contract():
    raw = json.loads(FIXTURE.read_text())
    raw.update(
        {
            "target_class": "DATABASE",
            "audit_trail_id": "trail-001",
            "audit_location": "UNIFIED_AUDIT_TRAIL",
            "trail_source": "UNIFIED_AUDIT_TRAIL",
            "external_user_id": "external-001",
            "target_user": "APP_USER",
            "peer_target_database_key": "peer-001",
            "application_contexts": [{"namespace": "USERENV", "attribute": "MODULE"}],
            "extended_event_attributes": {"proxy_user": "PROXY_USER"},
            "fga_policy_name": "POLICY_001",
        }
    )
    event = normalize_event(raw, config())
    assert event["target_class"] == "DATABASE"
    assert event["audit_trail_id"] == "trail-001"
    assert event["trail_source"] == "UNIFIED_AUDIT_TRAIL"
    assert json.loads(event["application_contexts"])[0]["namespace"] == "USERENV"
    assert json.loads(event["extended_event_attributes"])["proxy_user"] == "PROXY_USER"
    assert event["schema_version"] == "2.0"
