#!/usr/bin/env python3
"""Live cap-profile E2E validation with redacted evidence."""

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="cap")
    parser.add_argument("--compartment-id", required=True)
    parser.add_argument("--invoke-function-id")
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

    if args.invoke_function_id:
        management = oci.functions.FunctionsManagementClient(config)
        invoke_endpoint = management.get_function(
            args.invoke_function_id
        ).data.invoke_endpoint
        functions = oci.functions.FunctionsInvokeClient(
            config, service_endpoint=invoke_endpoint
        )
        functions.invoke_function(
            args.invoke_function_id,
            invoke_function_body=b"{}",
            fn_invoke_type="sync",
        )

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
    deadline = time.monotonic() + args.poll_seconds
    rows = []
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
        if rows:
            break
        time.sleep(15)

    if args.deploy_dashboards and not parse_failures and rows:
        run(
            [
                sys.executable,
                "scripts/deploy_dashboards.py",
                "--profile",
                args.profile,
                "--compartment-id",
                args.compartment_id,
            ]
        )

    expected_names = {
        f"Data Safe Audit | {tab['label']}"
        for tab in json.loads((ROOT / "dashboards" / "catalog.json").read_text())["tabs"]
    }
    deployed = md.list_management_dashboards(compartment_id=args.compartment_id).data.items
    deployed_names = {item.display_name for item in deployed}
    report = {
        "schemaVersion": "1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "profile": args.profile,
        "region": config["region"],
        "checks": {
            "dashboard_bundle_current": True,
            "query_count": len(list(QUERY_DIR.glob("*.json"))),
            "parse_failures": parse_failures,
            "log_analytics_rows_available": bool(rows),
            "dashboard_count_expected": len(expected_names),
            "dashboard_count_present": len(expected_names & deployed_names),
        },
        "ready": not parse_failures
        and bool(rows)
        and (not args.deploy_dashboards or expected_names <= deployed_names),
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
