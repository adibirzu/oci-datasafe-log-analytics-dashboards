#!/usr/bin/env python3
"""Plan, confirm, apply, and verify a scoped solution destroy."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import oci

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "dashboards" / "catalog.json"
DETECTIONS = ROOT / "terraform" / "detections.json"


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        command, cwd=ROOT, check=True, text=True, capture_output=capture
    )


def dashboard_names() -> set[str]:
    catalog = json.loads(CATALOG.read_text())
    return {f"Data Safe Audit | {tab['label']}" for tab in catalog["tabs"]}


def delete_dashboards(profile: str, compartment_id: str) -> int:
    config = oci.config.from_file(profile_name=profile)
    client = oci.management_dashboard.DashxApisClient(config)
    expected = dashboard_names()
    removed = 0
    for item in client.list_management_dashboards(compartment_id=compartment_id).data.items:
        if item.display_name not in expected:
            continue
        current = client.get_management_dashboard(item.id)
        client.delete_management_dashboard(
            item.id, if_match=current.headers.get("etag")
        )
        removed += 1
    remaining = {
        item.display_name
        for item in client.list_management_dashboards(
            compartment_id=compartment_id
        ).data.items
        if item.display_name in expected
    }
    if remaining:
        raise RuntimeError(f"dashboard cleanup incomplete: {len(remaining)} remain")
    return removed


def delete_detection_schedules(
    profile: str, compartment_id: str, deployment_name: str
) -> int:
    config = oci.config.from_file(profile_name=profile)
    client = oci.log_analytics.LogAnalyticsClient(config)
    namespace = client.list_namespaces(config["tenancy"]).data.items[0].namespace_name
    tasks = oci.pagination.list_call_get_all_results(
        client.list_scheduled_tasks,
        namespace,
        compartment_id=compartment_id,
        task_type="SAVED_SEARCH",
    ).data
    expected = f"{deployment_name} - "
    removed = 0
    for item in tasks:
        if (item.display_name or "").startswith(expected):
            client.delete_scheduled_task(namespace, item.id)
            removed += 1
    return removed


def delete_detection_searches(
    profile: str, compartment_id: str, deployment_name: str
) -> int:
    config = oci.config.from_file(profile_name=profile)
    client = oci.management_dashboard.DashxApisClient(config)
    titles = {
        f"{deployment_name} | {item['title']}"
        for item in json.loads(DETECTIONS.read_text()).values()
    }
    searches = oci.pagination.list_call_get_all_results(
        client.list_management_saved_searches,
        compartment_id=compartment_id,
    ).data
    removed = 0
    for item in searches:
        if item.display_name not in titles:
            continue
        current = client.get_management_saved_search(item.id)
        client.delete_management_saved_search(
            item.id, if_match=current.headers.get("etag")
        )
        removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--solution-compartment-id", required=True)
    parser.add_argument("--deployment-name", required=True)
    parser.add_argument("--tfvars", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--confirm",
        help="Required with --apply; must exactly match --deployment-name.",
    )
    args = parser.parse_args()
    if not args.tfvars.is_file():
        parser.error("--tfvars must name an existing untracked file")
    if args.apply and args.confirm != args.deployment_name:
        parser.error("--confirm must exactly match --deployment-name")

    run([sys.executable, "scripts/tenant_leak_check.py"])
    run(["terraform", "-chdir=terraform", "init", "-backend=false"])
    plan = ROOT / "terraform" / ".destroy-all.plan"
    run(
        [
            "terraform",
            "-chdir=terraform",
            "plan",
            "-destroy",
            f"-var-file={args.tfvars.resolve()}",
            f"-out={plan.name}",
        ]
    )
    shown = run(
        ["terraform", "-chdir=terraform", "show", "-json", plan.name],
        capture=True,
    )
    payload = json.loads(shown.stdout)
    changes = [
        item["address"]
        for item in payload.get("resource_changes", [])
        if "delete" in item["change"]["actions"]
    ]
    print(json.dumps({"destroy_count": len(changes), "deployment": args.deployment_name}))
    if not args.apply:
        print(json.dumps({"status": "planned", "confirmation": args.deployment_name}))
        return 0

    schedules_removed = delete_detection_schedules(
        args.profile, args.solution_compartment_id, args.deployment_name
    )
    searches_removed = delete_detection_searches(
        args.profile, args.solution_compartment_id, args.deployment_name
    )
    run(["terraform", "-chdir=terraform", "apply", "-auto-approve", plan.name])
    removed = delete_dashboards(args.profile, args.solution_compartment_id)
    state = run(["terraform", "-chdir=terraform", "state", "list"], capture=True)
    if state.stdout.strip():
        raise RuntimeError("Terraform state is not empty after destroy")
    print(
        json.dumps(
            {
                "status": "destroyed",
                "dashboards_removed": removed,
                "detection_schedules_removed": schedules_removed,
                "detection_searches_removed": searches_removed,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
