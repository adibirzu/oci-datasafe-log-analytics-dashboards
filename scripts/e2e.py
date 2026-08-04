#!/usr/bin/env python3
"""Live customer-context E2E validation with redacted evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import oci

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from oci_datasafe_exporter.oci_response import response_bytes  # noqa: E402

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


def _attribute(item: object, name: str):
    """Read an SDK-model or fixture attribute without exposing resource identities."""
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def scheduled_task_unhealthy_count(tasks: list[object], deployment_name: str) -> int:
    """Count solution tasks that cannot currently produce a healthy metric stream.

    A newly reconciled task has no execution result yet, so an absent
    ``last_execution_status`` is acceptable. A recorded failure, a paused or
    blocked task, or a non-active resource is not.
    """
    prefix = f"{deployment_name} - "
    return sum(
        _attribute(task, "lifecycle_state") != "ACTIVE"
        or _attribute(task, "task_status") != "READY"
        or _attribute(task, "last_execution_status") == "FAILED"
        for task in tasks
        if str(_attribute(task, "display_name") or "").startswith(prefix)
    )


def disabled_or_inactive_alarm_count(alarms: list[object], deployment_name: str) -> int:
    """Count solution alarms that cannot notify despite being present."""
    prefix = f"{deployment_name} | "
    return sum(
        not _attribute(alarm, "is_enabled") or _attribute(alarm, "lifecycle_state") != "ACTIVE"
        for alarm in alarms
        if str(_attribute(alarm, "display_name") or "").startswith(prefix)
    )


def function_export_count(payload: object) -> int:
    """Decode the function's privacy-safe export receipt and validate its shape."""
    try:
        receipt = json.loads(response_bytes(payload).decode("utf-8"))
        exported = int(receipt["exported"])
    except (KeyError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Function invocation did not return a valid export receipt") from exc
    if exported < 0:
        raise RuntimeError("Function invocation returned an invalid export count")
    return exported


def content_reconcile_command(profile: str, compartment_id: str) -> list[str]:
    """Return the explicit repair command used only when requested."""
    return [
        sys.executable,
        "scripts/setup_log_analytics_content.py",
        "--profile",
        profile,
        "--compartment-id",
        compartment_id,
    ]


def source_query(export_run_id: str | None) -> str:
    query = "'Log Source' = 'OCI Data Safe Database Audit' and 'Schema Version' = '2.0'"
    if export_run_id:
        query += f" and 'Export Run ID' = '{export_run_id}'"
    return f"{query} | stats count as Events"


def dimension_query(export_run_id: str | None) -> str:
    query = "'Log Source' = 'OCI Data Safe Database Audit' and 'Schema Version' = '2.0'"
    if export_run_id:
        query += f" and 'Export Run ID' = '{export_run_id}'"
    return (
        f"{query} | stats distinctcount('Data Safe Target Name') as Targets, "
        "distinctcount('Database User') as Users, "
        "distinctcount('Operation') as Operations"
    )


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
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=600,
        help="Maximum wait for asynchronous Connector Hub ingestion (default: 600).",
    )
    parser.add_argument(
        "--reconcile-content",
        action="store_true",
        help="Repair Log Analytics fields, parser, and source before validation.",
    )
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
    if args.reconcile_content:
        run(content_reconcile_command(args.profile, args.compartment_id))

    invocation_exported = None
    export_run_id = None
    if args.require_function_export and not args.invoke_function_id:
        raise SystemExit("--require-function-export requires --invoke-function-id")
    if args.invoke_function_id:
        export_run_id = uuid.uuid4().hex
        management = oci.functions.FunctionsManagementClient(config)
        invoke_endpoint = management.get_function(args.invoke_function_id).data.invoke_endpoint
        functions = oci.functions.FunctionsInvokeClient(config, service_endpoint=invoke_endpoint)
        response = functions.invoke_function(
            args.invoke_function_id,
            invoke_function_body=json.dumps({"export_run_id": export_run_id}).encode(),
            fn_invoke_type="sync",
        )
        invocation_exported = function_export_count(response.data)

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

    current_source_query = source_query(export_run_id)
    deadline = time.monotonic() + args.poll_seconds
    rows = []
    source_event_count = 0
    while time.monotonic() < deadline:
        response = la.query(
            namespace,
            oci.log_analytics.models.QueryDetails(
                compartment_id=args.compartment_id,
                compartment_id_in_subtree=True,
                query_string=current_source_query,
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
    field_query = dimension_query(export_run_id)
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
    field_row = oci.util.to_dict(field_response.data.items[0]) if field_response.data.items else {}
    populated_dimensions = {
        name: int(field_row.get(name) or 0) for name in ("Targets", "Users", "Operations")
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
    detection_task_unhealthy_count = scheduled_task_unhealthy_count(
        scheduled_tasks, args.deployment_name
    )
    alarms = oci.pagination.list_call_get_all_results(
        monitoring.list_alarms,
        compartment_id=args.compartment_id,
    ).data
    detection_alarm_count = sum(
        (item.display_name or "").startswith(f"{args.deployment_name} | ") for item in alarms
    )
    detection_alarm_unhealthy_count = disabled_or_inactive_alarm_count(alarms, args.deployment_name)
    report = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "contextVerified": bool(config.get("tenancy") and config.get("region")),
        "checks": {
            "dashboard_bundle_current": True,
            "content_reconciled": args.reconcile_content,
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
            "detection_task_unhealthy_count": detection_task_unhealthy_count,
            "detection_alarm_count": detection_alarm_count,
            "detection_alarm_unhealthy_count": detection_alarm_unhealthy_count,
        },
        "ready": not parse_failures
        and (not args.require_function_export or (invocation_exported or 0) > 0)
        and source_event_count > 0
        and all(count > 0 for count in populated_dimensions.values())
        and all(count == 1 for count in deployed_counts.values())
        and detection_task_count == 8
        and detection_task_unhealthy_count == 0
        and detection_alarm_count == 8
        and detection_alarm_unhealthy_count == 0,
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


def safe_main() -> int:
    """Keep CLI failures safe for terminals, CI logs, and copied evidence."""
    try:
        return main()
    except oci.exceptions.ServiceError:
        print(json.dumps({"status": "error", "reason": "oci_service_error"}))
        return 2
    except Exception:  # noqa: BLE001
        print(json.dumps({"status": "error", "reason": "runtime_error"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(safe_main())
