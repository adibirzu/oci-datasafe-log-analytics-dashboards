#!/usr/bin/env python3
"""Read-only, redacted discovery for the Data Safe audit analytics stack."""

from __future__ import annotations

import argparse
import json
from collections import Counter

import oci
from setup_log_analytics_content import (
    PARSER_NAME,
    SOURCE_DISPLAY,
    SOURCE_INTERNAL,
    namespace_for,
)


def _all(call, *args, **kwargs):
    return oci.pagination.list_call_get_all_results(call, *args, **kwargs).data


def discover(
    profile: str,
    data_safe_compartment_id: str,
    solution_compartment_id: str,
    deployment_name: str,
) -> dict:
    config = oci.config.from_file(profile_name=profile)
    data_safe = oci.data_safe.DataSafeClient(config)
    log_analytics = oci.log_analytics.LogAnalyticsClient(config)
    dashboards = oci.management_dashboard.DashxApisClient(config)
    connector = oci.sch.ServiceConnectorClient(config)
    namespace = namespace_for(log_analytics, config["tenancy"])

    targets = _all(
        data_safe.list_target_databases,
        data_safe_compartment_id,
        compartment_id_in_subtree=True,
        access_level="ACCESSIBLE",
    )
    trails = _all(
        data_safe.list_audit_trails,
        data_safe_compartment_id,
        compartment_id_in_subtree=True,
        access_level="ACCESSIBLE",
    )
    profiles = _all(
        data_safe.list_audit_profiles,
        data_safe_compartment_id,
        compartment_id_in_subtree=True,
        access_level="ACCESSIBLE",
    )
    sources = _all(
        log_analytics.list_sources,
        namespace,
        solution_compartment_id,
        is_system="ALL",
    )
    source = next((item for item in sources if item.name == SOURCE_INTERNAL), None)
    source_detail = (
        log_analytics.get_source(namespace, SOURCE_INTERNAL, solution_compartment_id).data
        if source
        else None
    )
    parsers = _all(log_analytics.list_parsers, namespace, is_system="ALL")
    parser = next((item for item in parsers if item.name == PARSER_NAME), None)
    dashboard_items = dashboards.list_management_dashboards(
        compartment_id=solution_compartment_id
    ).data.items
    suite_counts = Counter(
        item.display_name
        for item in dashboard_items
        if item.display_name.startswith("Data Safe Audit |")
    )
    connectors = _all(
        connector.list_service_connectors,
        compartment_id=solution_compartment_id,
        display_name=f"{deployment_name}-logging-to-log-analytics",
    )

    target_states = Counter(str(item.lifecycle_state) for item in targets)
    target_types = Counter(
        str(getattr(item, "database_type", None) or "UNKNOWN") for item in targets
    )
    trail_states = Counter(
        str(getattr(item, "status", None) or getattr(item, "lifecycle_state", None))
        for item in trails
    )
    checks = {
        "active_targets": target_states.get("ACTIVE", 0),
        "target_count": len(targets),
        "audit_profile_count": len(profiles),
        "audit_trail_count": len(trails),
        "collecting_or_idle_trails": sum(
            trail_states.get(state, 0) for state in ("COLLECTING", "IDLE")
        ),
        "log_analytics_onboarded": True,
        "source_internal_name_correct": source is not None,
        "source_display_name_correct": bool(
            source_detail and source_detail.display_name == SOURCE_DISPLAY
        ),
        "source_parser_attached": bool(
            source_detail and any(item.name == PARSER_NAME for item in source_detail.parsers or [])
        ),
        "parser_present": parser is not None,
        "dashboard_count": sum(suite_counts.values()),
        "dashboard_unique_names": len(suite_counts),
        "dashboard_duplicate_count": sum(max(0, count - 1) for count in suite_counts.values()),
        "connector_count": len(connectors),
        "connector_active": bool(connectors and connectors[0].lifecycle_state == "ACTIVE"),
    }
    ready = (
        checks["active_targets"] > 0
        and checks["audit_trail_count"] > 0
        and checks["source_internal_name_correct"]
        and checks["source_display_name_correct"]
        and checks["source_parser_attached"]
        and checks["parser_present"]
        and checks["dashboard_unique_names"] == 7
        and checks["dashboard_duplicate_count"] == 0
        and checks["connector_active"]
    )
    return {
        "schemaVersion": "1.0",
        "profile": profile,
        "region": config["region"],
        "checks": checks,
        "inventory": {
            "target_lifecycle_states": dict(sorted(target_states.items())),
            "target_database_types": dict(sorted(target_types.items())),
            "audit_trail_states": dict(sorted(trail_states.items())),
        },
        "ready": ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="cap")
    parser.add_argument("--data-safe-compartment-id", required=True)
    parser.add_argument("--solution-compartment-id", required=True)
    parser.add_argument("--deployment-name", default="datasafe-audit")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = discover(
        args.profile,
        args.data_safe_compartment_id,
        args.solution_compartment_id,
        args.deployment_name,
    )
    print(json.dumps(report, indent=2))
    return 2 if args.strict and not report["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
