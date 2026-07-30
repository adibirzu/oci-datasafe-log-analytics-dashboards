"""OCI Functions handler."""

from __future__ import annotations

import json
import logging

from .config import ExportConfig
from .cursor import ObjectStorageCursorStore
from .exporter import AuditExporter
from .runtime import resource_principal_clients

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)


def run_export() -> dict[str, object]:
    config = ExportConfig.from_env()
    data_safe, logging_client, object_storage, namespace = resource_principal_clients()
    store = ObjectStorageCursorStore(
        object_storage,
        namespace,
        config.cursor_bucket_name,
        config.cursor_object_name,
    )
    result = AuditExporter(config, data_safe, logging_client, store).run()
    safe_result = {
        "queried": result.queried,
        "exported": result.exported,
        "duplicates": result.duplicates,
        "batches": result.batches,
        "truncated": result.truncated,
    }
    LOG.info("Data Safe export complete: %s", json.dumps(safe_result))
    return safe_result


def handler(ctx, data=None):
    from fdk import response

    try:
        result = run_export()
        return response.Response(
            ctx,
            response_data=json.dumps(result),
            headers={"Content-Type": "application/json"},
            status_code=200,
        )
    except Exception:
        LOG.exception("Data Safe audit export failed")
        return response.Response(
            ctx,
            response_data=json.dumps({"status": "error"}),
            headers={"Content-Type": "application/json"},
            status_code=500,
        )
