"""OCI Functions handler."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import oci

from .config import ExportConfig
from .cursor import ObjectStorageCursorStore
from .exporter import AuditExporter
from .runtime import resource_principal_clients, resource_principal_detection_clients

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)
EXPORT_RUN_ID = re.compile(r"[0-9a-f]{32}")
DETECTIONS_CATALOG = Path("/function/detections.json")


def _export_run_id(data) -> str | None:
    """Accept only the opaque E2E marker from an invocation body."""
    if data is None:
        return None
    try:
        raw = data.getvalue() if hasattr(data, "getvalue") else data
        if not raw:
            return None
        marker = json.loads(raw).get("export_run_id")
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return marker if isinstance(marker, str) and EXPORT_RUN_ID.fullmatch(marker) else None


def _error_reason(exc: Exception) -> str:
    """Expose only a stable, non-sensitive failure category to callers."""
    stage = getattr(exc, "stage", "")
    if stage.startswith("detection_"):
        return stage
    if isinstance(exc, oci.exceptions.ServiceError):
        service = getattr(exc, "target_service", "")
        if service == "data_safe":
            return "data_safe_service_error"
        if service == "object_storage":
            return "object_storage_service_error"
        if service in {"logging_ingestion", "logging"}:
            return "logging_service_error"
        if service in {"log_analytics", "dashx_apis"}:
            return "detection_service_error"
        return "oci_service_error"
    if isinstance(exc, ValueError):
        return "configuration_error"
    return "runtime_error"


def run_export(export_run_id: str | None = None) -> dict[str, object]:
    config = ExportConfig.from_env()
    data_safe, logging_client, object_storage, namespace = resource_principal_clients()
    store = ObjectStorageCursorStore(
        object_storage,
        namespace,
        config.cursor_bucket_name,
        config.cursor_object_name,
    )
    result = AuditExporter(config, data_safe, logging_client, store).run(export_run_id)
    safe_result = {
        "queried": result.queried,
        "exported": result.exported,
        "duplicates": result.duplicates,
        "batches": result.batches,
        "truncated": result.truncated,
    }
    if config.reconcile_detections:
        from deploy_detections import reconcile_detections

        rules = json.loads(DETECTIONS_CATALOG.read_text(encoding="utf-8"))
        log_analytics, dashboards = resource_principal_detection_clients()
        reconciliation = reconcile_detections(
            log_analytics=log_analytics,
            dashboards=dashboards,
            namespace=config.log_analytics_namespace,
            compartment_id=config.solution_compartment_id,
            scope_compartment_id=config.solution_compartment_id,
            deployment_name=config.deployment_name,
            interval=config.detection_interval,
            rules=rules,
            retry_attempts=4,
            retry_delay_seconds=5,
        )
        safe_result["detections"] = reconciliation["detections"]
    LOG.info("Data Safe export complete: %s", json.dumps(safe_result))
    return safe_result


def handler(ctx, data=None):
    from fdk import response

    try:
        result = run_export(_export_run_id(data))
        return response.Response(
            ctx,
            response_data=json.dumps(result),
            headers={"Content-Type": "application/json"},
            status_code=200,
        )
    except Exception as exc:
        LOG.exception("Data Safe audit export failed")
        return response.Response(
            ctx,
            response_data=json.dumps({"status": "error", "reason": _error_reason(exc)}),
            headers={"Content-Type": "application/json"},
            status_code=500,
        )
