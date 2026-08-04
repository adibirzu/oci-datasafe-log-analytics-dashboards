#!/usr/bin/env python3
"""Read-only OCI readiness checks with redacted output."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta

import oci


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--data-safe-compartment-id")
    parser.add_argument("--solution-compartment-id")
    args = parser.parse_args()
    config = oci.config.from_file(profile_name=args.profile)
    data_safe_compartment_id = args.data_safe_compartment_id or config["tenancy"]
    solution_compartment_id = args.solution_compartment_id or config["tenancy"]
    identity = oci.identity.IdentityClient(config)
    tenancy = identity.get_tenancy(config["tenancy"]).data
    data_safe = oci.data_safe.DataSafeClient(config)
    log_analytics = oci.log_analytics.LogAnalyticsClient(config)

    targets = oci.pagination.list_call_get_all_results(
        data_safe.list_target_databases,
        compartment_id=data_safe_compartment_id,
        compartment_id_in_subtree=True,
        access_level="ACCESSIBLE",
    ).data
    end = datetime.now(UTC)
    start = end - timedelta(days=7)
    scim = (
        f'(auditEventTime ge "{start.isoformat(timespec="milliseconds").replace("+00:00", "Z")}") '
        f'and (auditEventTime le "{end.isoformat(timespec="milliseconds").replace("+00:00", "Z")}")'
    )
    events = data_safe.list_audit_events(
        compartment_id=data_safe_compartment_id,
        compartment_id_in_subtree=True,
        access_level="ACCESSIBLE",
        scim_query=scim,
        limit=1,
    ).data.items
    namespaces = log_analytics.list_namespaces(config["tenancy"]).data.items
    namespace = namespaces[0].namespace_name if namespaces else None
    log_groups = []
    if namespace:
        log_groups = oci.pagination.list_call_get_all_results(
            log_analytics.list_log_analytics_log_groups,
            namespace,
            compartment_id=solution_compartment_id,
        ).data
    report = {
        "context_verified": bool(tenancy.name and config["region"]),
        "checks": {
            "authentication": True,
            "active_data_safe_targets": sum(
                target.lifecycle_state == "ACTIVE" for target in targets
            ),
            "recent_audit_event_available": bool(events),
            "log_analytics_onboarded": bool(namespace),
            "accessible_log_analytics_log_groups": len(log_groups),
        },
        "ready": bool(targets and events and namespace and log_groups),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
