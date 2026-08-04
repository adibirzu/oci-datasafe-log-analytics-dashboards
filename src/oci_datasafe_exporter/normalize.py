"""Stable, privacy-aware Data Safe audit event normalization."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import oci

from .config import ExportConfig

FIELD_ALIASES = {
    "id": "Data Safe Event ID",
    "compartment_id": "Data Safe Compartment ID",
    "audit_event_time": "Audit Event Time",
    "time_collected": "Collection Time",
    "target_name": "Data Safe Target Name",
    "target_id": "Data Safe Target ID",
    "database_unique_name": "Database Unique Name",
    "database_type": "Database Type",
    "target_class": "Target Class",
    "db_user_name": "Database User",
    "operation": "Operation",
    "operation_status": "Operation Status",
    "event_name": "Event Name",
    "action_taken": "Action Taken",
    "client_ip": "Client IP",
    "client_hostname": "Client Host",
    "client_program": "Client Program",
    "client_id": "Client ID",
    "os_user_name": "OS User",
    "os_terminal": "OS Terminal",
    "object_name": "Object Name",
    "object_type": "Object Type",
    "object_owner": "Object Owner",
    "audit_policies": "Audit Policies",
    "audit_type": "Audit Type",
    "audit_trail_id": "Audit Trail ID",
    "audit_location": "Audit Location",
    "trail_source": "Trail Source",
    "error_code": "Error Code",
    "error_message": "Error Message",
    "admin_user": "Admin User",
    "common_user": "Common User",
    "sensitive_activity": "Sensitive Activity",
    "ds_activity": "Data Safe Activity",
    "command_text": "SQL Text",
    "command_param": "SQL Parameters",
    "external_user_id": "External User ID",
    "target_user": "Target User",
    "peer_target_database_key": "Peer Target Database Key",
    "application_contexts": "Application Contexts",
    "extended_event_attributes": "Extended Event Attributes",
    "fga_policy_name": "FGA Policy Name",
    "export_run_id": "Export Run ID",
}

COMPLEX_STRING_FIELDS = {
    "application_contexts",
    "audit_policies",
    "extended_event_attributes",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _stable_id(raw: dict[str, Any]) -> str:
    existing = raw.get("id")
    if existing:
        return str(existing)
    basis = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(basis.encode()).hexdigest()


def _pseudonymize_ip(value: Any, salt: str) -> str | None:
    if not value:
        return None
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()
    return f"ip-{digest[:20]}"


def normalize_event(event: Any, config: ExportConfig) -> dict[str, Any]:
    raw = oci.util.to_dict(event)
    raw["id"] = _stable_id(raw)

    if config.hash_client_ip:
        raw["client_ip"] = _pseudonymize_ip(raw.get("client_ip"), config.client_ip_hash_salt)
    if not config.include_sql_text:
        raw.pop("command_text", None)
    if not config.include_command_parameters:
        raw.pop("command_param", None)

    # Keep transport keys JSONPath-safe. Log Analytics maps these stable wire
    # names to the reader-facing display fields in FIELD_ALIASES.
    normalized = {
        source_name: (
            json.dumps(_json_safe(raw.get(source_name)), sort_keys=True, separators=(",", ":"))
            if source_name in COMPLEX_STRING_FIELDS
            and isinstance(raw.get(source_name), (dict, list, tuple))
            else _json_safe(raw.get(source_name))
        )
        for source_name in FIELD_ALIASES
        if source_name in raw
    }
    normalized["schema_version"] = "2.0"
    return normalized


def event_id(event: dict[str, Any]) -> str:
    return str(event["id"])
