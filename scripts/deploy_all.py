#!/usr/bin/env python3
"""One-run local Terraform deployment with exact-plan apply and live acceptance."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--data-safe-compartment-id", required=True)
    parser.add_argument("--solution-compartment-id", required=True)
    parser.add_argument("--deployment-name", default="datasafe-audit")
    parser.add_argument(
        "--tfvars",
        type=Path,
        required=True,
        help="Untracked Terraform variables file; credentials must not be included.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--lookback-minutes", type=int, default=1440)
    args = parser.parse_args()
    if not args.tfvars.is_file():
        parser.error("--tfvars must name an existing untracked variables file")

    run([sys.executable, "scripts/build_dashboard_bundle.py", "--check"])
    run([sys.executable, "scripts/build_orm_package.py"])
    run(["terraform", "-chdir=terraform", "init", "-backend=false"])
    run(["terraform", "-chdir=terraform", "validate"])
    plan = ROOT / "terraform" / ".deploy-all.plan"
    run(
        [
            "terraform",
            "-chdir=terraform",
            "plan",
            f"-var-file={args.tfvars.resolve()}",
            f"-out={plan.name}",
        ]
    )
    shown = run(
        ["terraform", "-chdir=terraform", "show", "-json", plan.name],
        capture=True,
    )
    payload = json.loads(shown.stdout)
    actions = [
        "/".join(item["change"]["actions"])
        for item in payload.get("resource_changes", [])
        if item["change"]["actions"] != ["no-op"]
    ]
    print(json.dumps({"planned_changes": len(actions), "actions": actions}))
    if not args.apply:
        print(json.dumps({"status": "planned", "next": "rerun with --apply"}))
        return 0

    run(["terraform", "-chdir=terraform", "apply", "-auto-approve", plan.name])
    run(
        [
            sys.executable,
            "scripts/setup_log_analytics_content.py",
            "--profile",
            args.profile,
            "--compartment-id",
            args.solution_compartment_id,
        ]
    )
    run(
        [
            sys.executable,
            "scripts/deploy_dashboards.py",
            "--profile",
            args.profile,
            "--compartment-id",
            args.solution_compartment_id,
            "--cleanup-duplicates",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/e2e.py",
            "--profile",
            args.profile,
            "--compartment-id",
            args.solution_compartment_id,
            "--lookback-minutes",
            str(args.lookback_minutes),
        ]
    )
    run(
        [
            sys.executable,
            "scripts/discover.py",
            "--profile",
            args.profile,
            "--data-safe-compartment-id",
            args.data_safe_compartment_id,
            "--solution-compartment-id",
            args.solution_compartment_id,
            "--deployment-name",
            args.deployment_name,
            "--strict",
        ]
    )
    print(json.dumps({"status": "applied-and-verified"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
