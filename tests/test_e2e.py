import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("e2e", ROOT / "scripts" / "e2e.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_aggregate_count_rejects_zero_value_row_as_evidence():
    assert MODULE.aggregate_count([{"Events": 0}]) == 0
    assert MODULE.aggregate_count([{"Events": "0"}]) == 0
    assert MODULE.aggregate_count([]) == 0


def test_aggregate_count_accepts_positive_source_evidence():
    assert MODULE.aggregate_count([{"Events": 6413}]) == 6413


def test_scheduled_task_health_accepts_ready_unexecuted_task():
    tasks = [
        {
            "display_name": "tenant-neutral - Failed Login Spike",
            "lifecycle_state": "ACTIVE",
            "task_status": "READY",
            "last_execution_status": None,
        }
    ]
    assert MODULE.scheduled_task_unhealthy_count(tasks, "tenant-neutral") == 0


def test_scheduled_task_health_rejects_failed_or_non_ready_task():
    tasks = [
        {
            "display_name": "tenant-neutral - Failed Login Spike",
            "lifecycle_state": "ACTIVE",
            "task_status": "READY",
            "last_execution_status": "FAILED",
        },
        {
            "display_name": "tenant-neutral - Database Error Spike",
            "lifecycle_state": "ACTIVE",
            "task_status": "PAUSED",
            "last_execution_status": "SUCCEEDED",
        },
    ]
    assert MODULE.scheduled_task_unhealthy_count(tasks, "tenant-neutral") == 2


def test_alarm_health_rejects_disabled_or_inactive_solution_alarms():
    alarms = [
        {
            "display_name": "tenant-neutral | Failed Login Spike",
            "is_enabled": True,
            "lifecycle_state": "ACTIVE",
        },
        {
            "display_name": "tenant-neutral | Database Error Spike",
            "is_enabled": False,
            "lifecycle_state": "ACTIVE",
        },
        {
            "display_name": "tenant-neutral | Privilege Change",
            "is_enabled": True,
            "lifecycle_state": "DELETED",
        },
    ]
    assert MODULE.disabled_or_inactive_alarm_count(alarms, "tenant-neutral") == 2


class StreamingResponse:
    def __init__(self, payload):
        self.data = payload


def test_function_export_count_decodes_oci_streaming_response():
    assert MODULE.function_export_count(StreamingResponse(b'{"exported": 3}')) == 3


def test_function_export_count_rejects_non_receipt_response():
    with pytest.raises(RuntimeError, match="valid export receipt"):
        MODULE.function_export_count(StreamingResponse(b'{"status": "error"}'))


def test_safe_main_redacts_oci_service_metadata(monkeypatch, capsys):
    def fail():
        raise MODULE.oci.exceptions.ServiceError(
            status=400,
            code="InvalidParameter",
            headers={},
            message="tenant-specific message must not be printed",
        )

    monkeypatch.setattr(MODULE, "main", fail)
    assert MODULE.safe_main() == 2
    assert json.loads(capsys.readouterr().out) == {
        "status": "error",
        "reason": "oci_service_error",
    }


def test_content_reconcile_requires_an_explicit_command_path():
    assert MODULE.content_reconcile_command("customer-profile", "customer-compartment") == [
        MODULE.sys.executable,
        "scripts/setup_log_analytics_content.py",
        "--profile",
        "customer-profile",
        "--compartment-id",
        "customer-compartment",
    ]


def test_current_export_queries_are_correlated_to_the_invocation_marker():
    marker = "0" * 32
    assert f"'Export Run ID' = '{marker}'" in MODULE.source_query(marker)
    assert f"'Export Run ID' = '{marker}'" in MODULE.dimension_query(marker)
    assert "Export Run ID" not in MODULE.source_query(None)
