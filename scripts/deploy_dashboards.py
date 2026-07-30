#!/usr/bin/env python3
"""Import the generated Data Safe dashboard suite into OCI."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

import oci

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dashboards" / "generated_bundle.json"


def replace_compartment(value, compartment_id: str):
    if isinstance(value, str):
        return value.replace("${compartment_id}", compartment_id)
    if isinstance(value, list):
        return [replace_compartment(item, compartment_id) for item in value]
    if isinstance(value, dict):
        return {key: replace_compartment(item, compartment_id) for key, item in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="cap")
    parser.add_argument("--compartment-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    payload = json.loads(BUNDLE.read_text())
    dashboards = replace_compartment(deepcopy(payload["dashboards"]), args.compartment_id)
    if args.dry_run:
        print(json.dumps({"dashboards": len(dashboards), "status": "planned"}))
        return 0
    config = oci.config.from_file(profile_name=args.profile)
    client = oci.management_dashboard.DashxApisClient(config)
    details = oci.management_dashboard.models.ManagementDashboardImportDetails(
        dashboards=dashboards
    )
    client.import_dashboard(details)
    print(json.dumps({"dashboards": len(dashboards), "status": "imported"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
