import pytest

from oci_datasafe_exporter.config import ExportConfig


def test_required_configuration_fails_closed(monkeypatch):
    for name in ("DATA_SAFE_COMPARTMENT_ID", "LOGGING_LOG_ID", "CURSOR_BUCKET_NAME"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="missing required configuration"):
        ExportConfig.from_env()


def test_ip_hashing_requires_a_secret_salt(monkeypatch):
    monkeypatch.setenv("DATA_SAFE_COMPARTMENT_ID", "compartment")
    monkeypatch.setenv("LOGGING_LOG_ID", "log")
    monkeypatch.setenv("CURSOR_BUCKET_NAME", "bucket")
    monkeypatch.setenv("HASH_CLIENT_IP", "true")
    monkeypatch.setenv("CLIENT_IP_HASH_SALT", "short")
    with pytest.raises(ValueError, match="at least 16"):
        ExportConfig.from_env()


def test_default_config_does_not_export_sql_or_bind_values(monkeypatch):
    monkeypatch.setenv("DATA_SAFE_COMPARTMENT_ID", "compartment")
    monkeypatch.setenv("LOGGING_LOG_ID", "log")
    monkeypatch.setenv("CURSOR_BUCKET_NAME", "bucket")
    monkeypatch.setenv("CLIENT_IP_HASH_SALT", "a-secure-test-salt")
    config = ExportConfig.from_env()
    assert config.include_sql_text is False
    assert config.include_command_parameters is False
    assert config.hash_client_ip is True


def test_detection_reconciliation_requires_only_its_runtime_inputs(monkeypatch):
    monkeypatch.setenv("DATA_SAFE_COMPARTMENT_ID", "compartment")
    monkeypatch.setenv("LOGGING_LOG_ID", "log")
    monkeypatch.setenv("CURSOR_BUCKET_NAME", "bucket")
    monkeypatch.setenv("CLIENT_IP_HASH_SALT", "x" * 16)
    monkeypatch.setenv("RECONCILE_DETECTIONS", "true")
    with pytest.raises(ValueError, match="missing detection reconciliation configuration"):
        ExportConfig.from_env()


def test_detection_reconciliation_accepts_complete_tenant_runtime_inputs(monkeypatch):
    for name, value in {
        "DATA_SAFE_COMPARTMENT_ID": "data-safe-compartment",
        "LOGGING_LOG_ID": "log",
        "CURSOR_BUCKET_NAME": "bucket",
        "CLIENT_IP_HASH_SALT": "x" * 16,
        "RECONCILE_DETECTIONS": "true",
        "LOG_ANALYTICS_NAMESPACE": "customer-namespace",
        "SOLUTION_COMPARTMENT_ID": "solution-compartment",
        "DEPLOYMENT_NAME": "audit-demo",
        "DETECTION_INTERVAL": "PT15M",
    }.items():
        monkeypatch.setenv(name, value)
    config = ExportConfig.from_env()
    assert config.reconcile_detections is True
    assert config.detection_interval == "PT15M"
