#!/usr/bin/env python3
"""Send one explicitly synthetic audit-shaped record to the configured OCI log."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime

import oci

LOG_TYPE = "com.oraclecloud.logging.custom.datasafe.audit"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="cap")
    parser.add_argument("--log-id", required=True)
    parser.add_argument(
        "--acknowledge-synthetic",
        action="store_true",
        help="Required acknowledgement that this writes a fabricated test record.",
    )
    args = parser.parse_args()
    if not args.acknowledge_synthetic:
        parser.error("--acknowledge-synthetic is required")

    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    event_id = f"synthetic-e2e-{uuid.uuid4()}"
    event = {
        "id": event_id,
        "audit_event_time": now,
        "time_collected": now,
        "target_name": "synthetic-cap-e2e",
        "database_type": "SYNTHETIC",
        "db_user_name": "SYNTHETIC_USER",
        "operation": "LOGIN",
        "operation_status": "SUCCESS",
        "event_name": "SYNTHETIC_E2E",
        "event_type": "Test",
        "admin_user": 0,
        "common_user": 0,
        "sensitive_activity": 0,
        "ds_activity": 0,
        "schema_version": "1.0",
    }
    config = oci.config.from_file(profile_name=args.profile)
    client = oci.loggingingestion.LoggingClient(config)
    details = oci.loggingingestion.models.PutLogsDetails(
        specversion="1.0",
        log_entry_batches=[
            oci.loggingingestion.models.LogEntryBatch(
                entries=[
                    oci.loggingingestion.models.LogEntry(
                        data=json.dumps(event, separators=(",", ":")),
                        id=event_id,
                        time=now,
                    )
                ],
                source="OCIDataSafeSyntheticE2E",
                type=LOG_TYPE,
                subject="OracleDatabaseAuditSynthetic",
                defaultlogentrytime=now,
            )
        ],
    )
    client.put_logs(args.log_id, details)
    print(json.dumps({"status": "sent", "synthetic": True, "record_count": 1}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
