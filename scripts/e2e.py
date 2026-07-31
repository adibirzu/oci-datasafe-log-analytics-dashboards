#!/usr/bin/env python3
"""Live customer-context E2E validation with redacted evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import oci

ROOT = Path(__file__).resolve().parents[1]
QUERY_DIR = ROOT / "dashboards" / "queries"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)  # noqa: S603


def query_window(lookback_minutes: int) -> oci.log_analytics.models.TimeRange:
    end = datetime.now(UTC)
    start = end - timedelta(minutes=lookback_minutes)
    return oci.log_analytics.models.TimeRange(
        time_start=start,
        time_end=end,
        time_zone="UTC",
    )


def aggregate_count(rows: list[object], field: str = "Events") -> int:
    """Return an aggregate count without treating a zero-valued row as evidence."""
    if not rows:
        return 0
    first = oci.util.to_dict(rows[0])
    try:
        return int(first.get(field) or 0)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--compartment-id", required=True)
    parser.add_argument("--deployment-name", default="datasafe-audit")
    parser.add_argument("--invoke-function-id")
    parser.add_argument(
        "--require-function-export",
        action="store_true",
        help="Require this invocation to export at least one schema-v2 Data Safe event.",
    )
    parser.add_argument("--lookback-minutes", type=int, default=60)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--deploy-dashboards", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    evidence_path = args.evidence or (
        ROOT / "evidence" / "live" / f"e2e-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    config = oci.config.from_file(profile_name=args.profile)
    la = oci.log_analytics.LogAnalyticsClient(config)
    md = oci.management_dashboard.DashxApisClient(config)
    monitoring = oci.monitoring.MonitoringClient(config)
    namespace = la.list_namespaces(config["tenancy"]).data.items[0].namespace_name

    run([sys.executable, "scripts/build_dashboard_bundle.py", "--check"])
    run(
        [
            sys.executable,
            "scripts/setup_log_analytics_content.py",
            "--profile",
            args.profile,
            "--compartment-id",
            args.compartment_id,
        ]
    )

    invocation_exported = None
    if args.require_function_export and not args.invoke_function_id:
        raise SystemExit("--require-function-export requires --invoke-function-id")
    if args.invoke_function_id:
        management = oci.functions.FunctionsManagementClient(config)
        invoke_endpoint = management.get_function(
            args.invoke_function_id
        ).data.invoke_endpoint
        functions = oci.functions.FunctionsInvokeClient(
            config, service_endpoint=invoke_endpoint
        )
        response = functions.invoke_function(
            args.invoke_function_id,
            invoke_function_body=b"{}",
            fn_invoke_type="sync",
        )
        payload = (
            response.data.content
            if hasattr(response.data, "content")
            else bytes(response.data)
        )
        invocation_exported = int(json.loads(payload.decode()).get("exported", 0))

    parse_failures = []
    for path in sorted(QUERY_DIR.glob("*.json")):
        query = json.loads(path.read_text())["query"]
        try:
            la.parse_query(
                namespace,
                oci.log_analytics.models.ParseQueryDetails(query_string=query, sub_system="LOG"),
            )
        except Exception as exc:
            parse_failures.append({"query": path.stem, "error": type(exc).__name__})

    source_query = "'Log Source' = 'OCI Data Safe Database Audit' | stats count as Events"
    if args.require_function_export:
        source_query = (
            "'Log Source' = 'OCI Data Safe Database Audit' "
            "and 'Schema Version' = '2.0' | stats count as Events"
        )
    deadline = time.monotonic() + args.poll_seconds
    rows = []
    source_event_count = 0
    while time.monotonic() < deadline:
        response = la.query(
            namespace,
            oci.log_analytics.models.QueryDetails(
                compartment_id=args.compartment_id,
                compartment_id_in_subtree=True,
                query_string=source_query,
                sub_system="LOG",
                time_filter=query_window(args.lookback_minutes),
                max_total_count=10,
            ),
        )
        rows = response.data.items
        source_event_count = aggregate_count(rows)
        if source_event_count > 0:
            break
        time.sleep(15)

    if args.deploy_dashboards and not parse_failures and source_event_count > 0:
        run(
            [
                sys.executable,
                "scripts/deploy_dashboards.py",
                "--profile",
                args.profile,
                "--compartment-id",
                args.compartment_id,
                "--cleanup-duplicates",
            ]
        )

    expected_names = {
        f"Data Safe Audit | {tab['label']}"
        for tab in json.loads((ROOT / "dashboards" / "catalog.json").read_text())["tabs"]
    }
    deployed = md.list_management_dashboards(compartment_id=args.compartment_id).data.items
    deployed_counts = {
        name: sum(item.display_name == name for item in deployed) for name in expected_names
    }
    field_query = (
        "'Log Source' = 'OCI Data Safe Database Audit' and 'Schema Version' = '2.0' "
        "| stats distinctcount('Data Safe Target Name') as Targets, "
        "distinctcount('Database User') as Users, "
        "distinctcount('Operation') as Operations"
    )
    field_response = la.query(
        namespace,
        oci.log_analytics.models.QueryDetails(
            compartment_id=args.compartment_id,
            compartment_id_in_subtree=True,
            query_string=field_query,
            sub_system="LOG",
            time_filter=query_window(args.lookback_minutes),
            max_total_count=10,
        ),
    )
    field_row = (
        oci.util.to_dict(field_response.data.items[0])
        if field_response.data.items
        else {}
    )
    populated_dimensions = {
        name: int(field_row.get(name) or 0)
        for name in ("Targets", "Users", "Operations")
    }
    scheduled_tasks = oci.pagination.list_call_get_all_results(
        la.list_scheduled_tasks,
        namespace,
        compartment_id=args.compartment_id,
        task_type="SAVED_SEARCH",
    ).data
    detection_task_count = sum(
        (item.display_name or "").startswith(f"{args.deployment_name} - ")
        for item in scheduled_tasks
    )
    alarms = oci.pagination.list_call_get_all_results(
        monitoring.list_alarms,
        compartment_id=args.compartment_id,
    ).data
    detection_alarm_count = sum(
        (item.display_name or "").startswith(f"{args.deployment_name} | ")
        for item in alarms
    )
    report = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "contextVerified": bool(config.get("tenancy") and config.get("region")),
        "checks": {
            "dashboard_bundle_current": True,
            "query_count": len(list(QUERY_DIR.glob("*.json"))),
            "parse_failures": parse_failures,
            "function_exported": invocation_exported,
            "log_analytics_event_count": source_event_count,
            "log_analytics_rows_available": source_event_count > 0,
            "populated_dimensions": populated_dimensions,
            "dashboard_count_expected": len(expected_names),
            "dashboard_count_present": sum(count > 0 for count in deployed_counts.values()),
            "dashboard_duplicate_count": sum(
                max(0, count - 1) for count in deployed_counts.values()
            ),
            "detection_task_count": detection_task_count,
            "detection_alarm_count": detection_alarm_count,
        },
        "ready": not parse_failures
        and (not args.require_function_export or (invocation_exported or 0) > 0)
        and source_event_count > 0
        and all(count > 0 for count in populated_dimensions.values())
        and all(count == 1 for count in deployed_counts.values())
        and detection_task_count == 8
        and detection_alarm_count == 8,
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
