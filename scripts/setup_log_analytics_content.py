#!/usr/bin/env python3
"""Idempotently create the Data Safe field, JSON parser, and source contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import oci
from oci.log_analytics.models import (
    LogAnalyticsField,
    LogAnalyticsParserField,
    UpsertLogAnalyticsFieldDetails,
    UpsertLogAnalyticsParserDetails,
)

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from oci_datasafe_exporter.normalize import FIELD_ALIASES  # noqa: E402

SOURCE_DISPLAY = "OCI Data Safe Database Audit"
SOURCE_INTERNAL = "com.oraclecloud.logging.custom.datasafe.audit"
PARSER_NAME = "ociDataSafeAuditJsonParser"
PARSER_DISPLAY = "OCI Data Safe Audit JSON Parser"
LONG_FIELDS = {"Admin User", "Common User", "Sensitive Activity", "Data Safe Activity"}
EVENT_EXAMPLE = {
    "id": "synthetic-event-001",
    "audit_event_time": "2026-07-30T12:00:00.000Z",
    "time_collected": "2026-07-30T12:01:00.000Z",
    "target_name": "example-target",
    "db_user_name": "APP_USER",
    "operation": "SELECT",
    "operation_status": "SUCCESS",
    "target_class": "DATABASE",
    "client_ip": "ip-00000000000000000000",
    "client_hostname": "example-client",
    "client_program": "example-program",
    "object_owner": "APP",
    "object_name": "ORDERS",
    "object_type": "TABLE",
    "audit_type": "STANDARD",
    "audit_trail_id": "synthetic-trail-001",
    "audit_location": "UNIFIED_AUDIT_TRAIL",
    "trail_source": "UNIFIED_AUDIT_TRAIL",
    "admin_user": 0,
    "common_user": 0,
    "sensitive_activity": 1,
    "ds_activity": 0,
    "export_run_id": "00000000000000000000000000000000",
    "schema_version": "2.0",
}
EXAMPLE = {
    "data": EVENT_EXAMPLE,
    "id": "synthetic-logging-record-001",
    "source": "OCIDataSafe",
    "specversion": "1.0",
    "subject": "OracleDatabaseAudit",
    "time": "2026-07-30T12:01:00.000Z",
    "type": SOURCE_INTERNAL,
}


def namespace_for(client, tenancy_id: str) -> str:
    response = client.list_namespaces(tenancy_id)
    if not response.data.items:
        raise RuntimeError("Oracle Log Analytics is not onboarded in this region")
    return response.data.items[0].namespace_name


def existing_fields(client, namespace: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    page = None
    while True:
        response = client.list_fields(namespace, limit=1000, page=page)
        for field in response.data.items:
            fields[field.display_name] = field.name
            fields[field.name] = field.name
        page = response.headers.get("opc-next-page")
        if not page:
            return fields


def ensure_fields(client, namespace: str) -> dict[str, str]:
    fields = existing_fields(client, namespace)
    required = list(FIELD_ALIASES.values()) + ["Schema Version"]
    for display_name in required:
        if display_name in fields:
            continue
        details = UpsertLogAnalyticsFieldDetails(
            display_name=display_name,
            data_type="Long" if display_name in LONG_FIELDS else "String",
            is_multi_valued=False,
        )
        response = client.upsert_field(namespace, details)
        fields[display_name] = response.data.name
    return existing_fields(client, namespace)


def ensure_parser(client, namespace: str, fields: dict[str, str]) -> None:
    mappings = []
    wire_fields = list(FIELD_ALIASES.items()) + [("schema_version", "Schema Version")]
    for sequence, (wire_name, display_name) in enumerate(wire_fields, start=1):
        internal = fields[display_name]
        mappings.append(
            LogAnalyticsParserField(
                field=LogAnalyticsField(name=internal),
                parser_field_name=internal,
                parser_field_sequence=sequence,
                storage_field_name=internal,
                # Connector Hub sends the value of OCI Logging's logContent
                # object. The Function payload is nested under logContent.data.
                structured_column_info=f"$.data.{wire_name}",
            )
        )
    content = json.dumps(EXAMPLE, indent=2)
    details = UpsertLogAnalyticsParserDetails(
        name=PARSER_NAME,
        display_name=PARSER_DISPLAY,
        description="Parses privacy-aware database audit events exported from OCI Data Safe.",
        type="JSON",
        language="en_US",
        encoding="UTF-8",
        is_default=True,
        is_single_line_content=False,
        is_system=False,
        header_content="$:0",
        content=content,
        example_content=content,
        field_maps=mappings,
    )
    kwargs = {}
    try:
        kwargs["if_match"] = client.get_parser(namespace, PARSER_NAME).headers.get("etag")
    except oci.exceptions.ServiceError as exc:
        if exc.status != 404:
            raise
    client.upsert_parser(namespace, details, **kwargs)


def ensure_source(profile: str, namespace: str, compartment_id: str, client) -> None:
    etag = None
    source_name = SOURCE_INTERNAL
    response = oci.pagination.list_call_get_all_results(
        client.list_sources,
        namespace,
        compartment_id,
        is_system="ALL",
    )
    # OCI Logging -> Log Analytics routing matches the custom log batch `type`
    # to the source's immutable internal name. A same-display-name source is not
    # equivalent and must not be reused.
    matches = [source for source in response.data if source.name == SOURCE_INTERNAL]
    if matches:
        source_name = matches[0].name
        etag = client.get_source(namespace, source_name, compartment_id).headers.get("etag")
    parsers = [{"name": PARSER_NAME, "isDefault": True}]
    entity_types = [
        {
            "entityType": "oci_generic_resource",
            "entityTypeCategory": "Undefined",
            "entityTypeDisplayName": "OCI Generic Resource",
        }
    ]
    with tempfile.TemporaryDirectory() as directory:
        parser_file = Path(directory) / "parsers.json"
        entity_file = Path(directory) / "entities.json"
        parser_file.write_text(json.dumps(parsers))
        entity_file.write_text(json.dumps(entity_types))
        command = [
            "oci",
            "log-analytics",
            "source",
            "upsert-source",
            "--profile",
            profile,
            "--namespace-name",
            namespace,
            "--name",
            source_name,
            "--description",
            "OCI Data Safe database audit events from OCI Logging.",
            "--type-name",
            "os_file",
            "--is-system",
            "false",
            "--is-for-cloud",
            "false",
            "--parsers",
            f"file://{parser_file}",
            "--entity-types",
            f"file://{entity_file}",
        ]
        # The service creates the immutable internal name from displayName on
        # first upsert. Bootstrap with the routing identifier, then update only
        # the reader-facing display name.
        if not etag:
            subprocess.run(  # noqa: S603
                [*command, "--display-name", SOURCE_INTERNAL],
                check=True,
                capture_output=True,
                text=True,
            )
            etag = client.get_source(namespace, SOURCE_INTERNAL, compartment_id).headers.get("etag")
        subprocess.run(  # noqa: S603
            [
                *command,
                "--display-name",
                SOURCE_DISPLAY,
                "--if-match",
                etag,
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--compartment-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "fields": len(set(FIELD_ALIASES.values())) + 1,
                    "parser": PARSER_NAME,
                    "source": SOURCE_DISPLAY,
                }
            )
        )
        return 0
    config = oci.config.from_file(profile_name=args.profile)
    client = oci.log_analytics.LogAnalyticsClient(config)
    namespace = namespace_for(client, config["tenancy"])
    fields = ensure_fields(client, namespace)
    ensure_parser(client, namespace, fields)
    ensure_source(args.profile, namespace, args.compartment_id, client)
    print(
        json.dumps(
            {
                "status": "ready",
                "fields": len(set(FIELD_ALIASES.values())) + 1,
                "parser": PARSER_NAME,
                "source": SOURCE_DISPLAY,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
