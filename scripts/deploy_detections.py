#!/usr/bin/env python3
"""Idempotently reconcile Log Analytics scheduled detections."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import oci

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "terraform" / "detections.json"
INTERVALS = {"PT5M", "PT10M", "PT15M", "PT30M", "PT1H"}


def saved_search_details(
    *,
    display_name: str,
    description: str,
    compartment_id: str,
    scope_compartment_id: str,
    query: str,
    update: bool = False,
):
    log_group_value = {
        "label": "Selected compartment",
        "value": scope_compartment_id,
    }
    scope_filters = {
        "LogGroup": {
            "flags": {"IncludeSubCompartments": True},
            "type": "LogGroup",
            "values": [log_group_value],
        },
        "Entity": {
            "flags": {
                "IncludeDependents": True,
                "ScopeCompartmentId": scope_compartment_id,
            },
            "type": "Entity",
            "values": [],
        },
        "LogSet": {"flags": {}, "type": "LogSet", "values": []},
        "filters": [
            {
                "flags": {"includeSubCompartments": True},
                "type": "LogGroup",
                "values": [log_group_value],
            },
            {
                "flags": {
                    "includeDependents": True,
                    "scopeCompartmentId": scope_compartment_id,
                },
                "type": "Entity",
                "values": [],
            },
            {"flags": {}, "type": "LogSet", "values": []},
        ],
        "isGlobal": False,
    }
    model = (
        oci.management_dashboard.models.UpdateManagementSavedSearchDetails
        if update
        else oci.management_dashboard.models.CreateManagementSavedSearchDetails
    )
    return model(
        display_name=display_name,
        provider_id="log-analytics",
        provider_name="Logging Analytics",
        provider_version="3.0.0",
        compartment_id=compartment_id,
        is_oob_saved_search=False,
        description=description,
        nls={},
        type="WIDGET_DONT_SHOW_IN_DASHBOARD",
        ui_config={
            "enableWidgetInApp": True,
            "queryString": query,
            "scopeFilters": scope_filters,
            "showTitle": True,
            "visualizationType": "summary_table",
            "visualizationOptions": {},
            "timeSelection": {"timePeriod": "l1h"},
            "vizType": "lxSavedSearchWidgetType",
        },
        data_config=[],
        screen_image=" ",
        metadata_version="2.0",
        widget_template="visualizations/chartWidgetTemplate.html",
        widget_vm="jet-modules/dashboards/widgets/lxSavedSearchWidget",
        parameters_config=[],
        features_config={
            "crossService": {"shared": True},
            "serviceTypes": ["log-analytics"],
        },
        drilldown_config=[],
        freeform_tags={
            "solution": "oci-datasafe-log-analytics",
            "managed-by": "deploy-detections",
        },
        defined_tags={},
    )


def task_details(
    *,
    display_name: str,
    description: str,
    saved_search_id: str,
    compartment_id: str,
    deployment_name: str,
    metric_name: str,
    interval: str,
) -> oci.log_analytics.models.CreateStandardTaskDetails:
    schedule_kwargs = {
        "type": "FIXED_FREQUENCY",
        "recurring_interval": interval,
        "repeat_count": -1,
        "misfire_policy": "RETRY_ONCE",
    }
    if "query_offset_secs" in oci.log_analytics.models.FixedFrequencySchedule().swagger_types:
        schedule_kwargs["query_offset_secs"] = 120
    task_kwargs = {
        "kind": "STANDARD",
        "display_name": display_name,
        "description": description,
        "compartment_id": compartment_id,
        "task_type": "SAVED_SEARCH",
        "action": oci.log_analytics.models.StreamAction(
            type="STREAM",
            saved_search_id=saved_search_id,
            saved_search_duration=interval,
            metric_extraction=oci.log_analytics.models.MetricExtraction(
                compartment_id=compartment_id,
                namespace="datasafe_audit",
                resource_group=deployment_name,
                metric_name=metric_name,
            ),
        ),
        "schedules": [oci.log_analytics.models.FixedFrequencySchedule(**schedule_kwargs)],
        "freeform_tags": {
            "solution": "oci-datasafe-log-analytics",
            "managed-by": "deploy-detections",
        },
    }
    supported = oci.log_analytics.models.CreateStandardTaskDetails().swagger_types
    return oci.log_analytics.models.CreateStandardTaskDetails(
        **{key: value for key, value in task_kwargs.items() if key in supported}
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--compartment-id", required=True)
    parser.add_argument("--deployment-name", required=True)
    parser.add_argument(
        "--scope-compartment-id",
        help="Log Analytics log-group compartment; defaults to --compartment-id.",
    )
    parser.add_argument("--interval", choices=sorted(INTERVALS), default="PT5M")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--replace-searches",
        action="store_true",
        help="Recreate only exact-name solution-owned searches before scheduling.",
    )
    args = parser.parse_args()
    scope_compartment_id = args.scope_compartment_id or args.compartment_id

    rules = json.loads(CATALOG.read_text())
    config = oci.config.from_file(profile_name=args.profile)
    la = oci.log_analytics.LogAnalyticsClient(config)
    md = oci.management_dashboard.DashxApisClient(config)
    namespace = la.list_namespaces(config["tenancy"]).data.items[0].namespace_name
    searches = oci.pagination.list_call_get_all_results(
        md.list_management_saved_searches,
        compartment_id=args.compartment_id,
    ).data
    grouped_searches: dict[str, list] = {}
    for item in searches:
        grouped_searches.setdefault(item.display_name, []).append(item)
    existing = oci.pagination.list_call_get_all_results(
        la.list_scheduled_tasks,
        namespace,
        compartment_id=args.compartment_id,
        task_type="SAVED_SEARCH",
    ).data
    existing_by_name = {item.display_name: item for item in existing}
    planned = []
    for key, rule in sorted(rules.items()):
        search_name = f"{args.deployment_name} | {rule['title']}"
        task_name = f"{args.deployment_name} - {rule['title']}"
        matches = sorted(
            grouped_searches.get(search_name, []),
            key=lambda item: (item.time_created, item.id),
            reverse=True,
        )
        current = existing_by_name.get(task_name)
        saved_search_id = matches[0].id if matches else None
        if not args.dry_run:
            desired = saved_search_details(
                display_name=search_name,
                description=rule["description"],
                compartment_id=args.compartment_id,
                scope_compartment_id=scope_compartment_id,
                query=rule["query"],
                update=bool(matches),
            )
            if matches and args.replace_searches:
                if current is not None:
                    la.delete_scheduled_task(namespace, current.id)
                    current = None
                for match in matches:
                    current_search = md.get_management_saved_search(match.id)
                    md.delete_management_saved_search(
                        match.id,
                        if_match=current_search.headers.get("etag"),
                    )
                saved_search_id = md.create_management_saved_search(
                    saved_search_details(
                        display_name=search_name,
                        description=rule["description"],
                        compartment_id=args.compartment_id,
                        scope_compartment_id=scope_compartment_id,
                        query=rule["query"],
                    )
                ).data.id
            elif matches:
                current_search = md.get_management_saved_search(saved_search_id)
                if current_search.data.type != "WIDGET_DONT_SHOW_IN_DASHBOARD":
                    if current is not None:
                        la.delete_scheduled_task(namespace, current.id)
                        current = None
                    md.delete_management_saved_search(
                        saved_search_id,
                        if_match=current_search.headers.get("etag"),
                    )
                    saved_search_id = md.create_management_saved_search(
                        saved_search_details(
                            display_name=search_name,
                            description=rule["description"],
                            compartment_id=args.compartment_id,
                            scope_compartment_id=scope_compartment_id,
                            query=rule["query"],
                        )
                    ).data.id
                else:
                    md.update_management_saved_search(
                        saved_search_id,
                        desired,
                        if_match=current_search.headers.get("etag"),
                    )
                for duplicate in matches[1:]:
                    duplicate_current = md.get_management_saved_search(duplicate.id)
                    md.delete_management_saved_search(
                        duplicate.id,
                        if_match=duplicate_current.headers.get("etag"),
                    )
            else:
                saved_search_id = md.create_management_saved_search(desired).data.id
        planned.append(
            (
                key,
                rule,
                task_name,
                saved_search_id,
                current,
            )
        )
    if args.dry_run:
        print(
            json.dumps(
                {
                    "detections": len(planned),
                    "existing_schedules": sum(item[4] is not None for item in planned),
                    "status": "planned",
                }
            )
        )
        return 0

    created = retained = 0
    for key, rule, task_name, saved_search_id, current in planned:
        if current is not None:
            details = la.get_scheduled_task(namespace, current.id).data
            action = details.action
            schedule = details.schedules[0]
            if (
                action.saved_search_id == saved_search_id
                and action.saved_search_duration == args.interval
                and schedule.recurring_interval == args.interval
            ):
                retained += 1
                continue
            la.delete_scheduled_task(namespace, current.id)
        details = task_details(
            display_name=task_name,
            description=rule["description"],
            saved_search_id=saved_search_id,
            compartment_id=args.compartment_id,
            deployment_name=args.deployment_name,
            metric_name=key,
            interval=args.interval,
        )
        for attempt in range(6):
            try:
                la.create_scheduled_task(namespace, details)
                created += 1
                break
            except oci.exceptions.ServiceError as exc:
                if exc.status != 400 or attempt == 5:
                    raise RuntimeError(
                        f"detection schedule creation failed for {key}: HTTP {exc.status}"
                    ) from None
                time.sleep(10)
    print(
        json.dumps(
            {
                "detections": len(planned),
                "created_or_replaced": created,
                "retained": retained,
                "status": "reconciled",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
