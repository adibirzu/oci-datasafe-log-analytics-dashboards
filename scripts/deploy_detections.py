#!/usr/bin/env python3
"""Idempotently reconcile Log Analytics scheduled detections."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import oci

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path(os.getenv("DETECTIONS_CATALOG", ROOT / "terraform" / "detections.json"))
INTERVALS = {"PT5M", "PT10M", "PT15M", "PT30M", "PT1H"}


class DetectionReconciliationError(RuntimeError):
    """A stable, non-sensitive category for a failed detection API call."""

    def __init__(self, stage: str):
        super().__init__(stage)
        self.stage = stage


def _service_error_stage(stage: str, exc: oci.exceptions.ServiceError) -> str:
    """Return a non-sensitive operation/status category for an OCI failure."""
    category = {
        400: "validation",
        401: "authorization",
        403: "authorization",
        404: "not_found",
        409: "conflict",
        412: "precondition",
        429: "throttled",
    }.get(exc.status, "service")
    return f"{stage.removesuffix('_error')}_{category}_error"


def detection_api_call(stage: str, call):
    try:
        return call()
    except oci.exceptions.ServiceError as exc:
        raise DetectionReconciliationError(_service_error_stage(stage, exc)) from exc


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


def saved_search_is_current(current: Any, desired: Any) -> bool:
    """Compare only solution-owned fields that OCI preserves for saved searches."""
    fields = (
        "display_name",
        "description",
        "provider_id",
        "provider_name",
        "provider_version",
        "type",
        "ui_config",
        "freeform_tags",
    )
    return all(getattr(current, field, None) == getattr(desired, field, None) for field in fields)


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


def reconcile_detections(
    *,
    log_analytics: Any,
    dashboards: Any,
    namespace: str,
    compartment_id: str,
    deployment_name: str,
    interval: str,
    rules: dict[str, dict[str, str]],
    scope_compartment_id: str | None = None,
    replace_searches: bool = False,
    retry_attempts: int = 6,
    retry_delay_seconds: int = 10,
) -> dict[str, int | str]:
    """Reconcile exact-name saved searches and schedules for one deployment.

    The caller supplies authenticated OCI clients so this same implementation
    works both from an operator profile and an OCI Functions resource principal.
    """
    if interval not in INTERVALS:
        raise ValueError(f"unsupported detection interval: {interval}")
    if retry_attempts < 1:
        raise ValueError("retry_attempts must be positive")
    scope_compartment_id = scope_compartment_id or compartment_id
    la = log_analytics
    md = dashboards
    searches = detection_api_call(
        "detection_saved_search_list_error",
        lambda: (
            oci.pagination.list_call_get_all_results(
                md.list_management_saved_searches,
                compartment_id=compartment_id,
            ).data
        ),
    )
    grouped_searches: dict[str, list] = {}
    for item in searches:
        grouped_searches.setdefault(item.display_name, []).append(item)
    existing = detection_api_call(
        "detection_scheduled_task_list_error",
        lambda: (
            oci.pagination.list_call_get_all_results(
                la.list_scheduled_tasks,
                namespace,
                compartment_id=compartment_id,
                task_type="SAVED_SEARCH",
            ).data
        ),
    )
    existing_by_name = {item.display_name: item for item in existing}
    planned = []
    for key, rule in sorted(rules.items()):
        search_name = f"{deployment_name} | {rule['title']}"
        task_name = f"{deployment_name} - {rule['title']}"
        matches = sorted(
            grouped_searches.get(search_name, []),
            key=lambda item: (item.time_created, item.id),
            reverse=True,
        )
        current = existing_by_name.get(task_name)
        saved_search_id = matches[0].id if matches else None
        desired = saved_search_details(
            display_name=search_name,
            description=rule["description"],
            compartment_id=compartment_id,
            scope_compartment_id=scope_compartment_id,
            query=rule["query"],
            update=bool(matches),
        )
        if matches and replace_searches:
            if current is not None:
                detection_api_call(
                    "detection_scheduled_task_delete_error",
                    lambda task_id=current.id: la.delete_scheduled_task(namespace, task_id),
                )
                current = None
            for match in matches:
                current_search = detection_api_call(
                    "detection_saved_search_get_error",
                    lambda search_id=match.id: md.get_management_saved_search(search_id),
                )
                current_etag = current_search.headers.get("etag")
                detection_api_call(
                    "detection_saved_search_delete_error",
                    lambda search_id=match.id, etag=current_etag: md.delete_management_saved_search(
                        search_id,
                        if_match=etag,
                    ),
                )
            create_details = saved_search_details(
                display_name=search_name,
                description=rule["description"],
                compartment_id=compartment_id,
                scope_compartment_id=scope_compartment_id,
                query=rule["query"],
            )
            saved_search_id = detection_api_call(
                "detection_saved_search_create_error",
                lambda details=create_details: md.create_management_saved_search(details).data.id,
            )
        elif matches:
            current_search = detection_api_call(
                "detection_saved_search_get_error",
                lambda search_id=saved_search_id: md.get_management_saved_search(search_id),
            )
            if current_search.data.type != "WIDGET_DONT_SHOW_IN_DASHBOARD":
                if current is not None:
                    detection_api_call(
                        "detection_scheduled_task_delete_error",
                        lambda task_id=current.id: la.delete_scheduled_task(namespace, task_id),
                    )
                    current = None
                current_etag = current_search.headers.get("etag")
                detection_api_call(
                    "detection_saved_search_delete_error",
                    lambda search_id=saved_search_id, etag=current_etag: (
                        md.delete_management_saved_search(
                            search_id,
                            if_match=etag,
                        )
                    ),
                )
                create_details = saved_search_details(
                    display_name=search_name,
                    description=rule["description"],
                    compartment_id=compartment_id,
                    scope_compartment_id=scope_compartment_id,
                    query=rule["query"],
                )
                saved_search_id = detection_api_call(
                    "detection_saved_search_create_error",
                    lambda details=create_details: (
                        md.create_management_saved_search(details).data.id
                    ),
                )
            else:
                if not saved_search_is_current(current_search.data, desired):
                    current_etag = current_search.headers.get("etag")
                    try:
                        detection_api_call(
                            "detection_saved_search_update_error",
                            lambda search_id=saved_search_id, details=desired, etag=current_etag: (
                                md.update_management_saved_search(
                                    search_id,
                                    details,
                                    if_match=etag,
                                )
                            ),
                        )
                    except DetectionReconciliationError as exc:
                        if exc.stage != "detection_saved_search_update_not_found_error":
                            raise
                        detection_api_call(
                            "detection_saved_search_delete_error",
                            lambda search_id=saved_search_id, etag=current_etag: (
                                md.delete_management_saved_search(
                                    search_id,
                                    if_match=etag,
                                )
                            ),
                        )
                        create_details = saved_search_details(
                            display_name=search_name,
                            description=rule["description"],
                            compartment_id=compartment_id,
                            scope_compartment_id=scope_compartment_id,
                            query=rule["query"],
                        )
                        saved_search_id = detection_api_call(
                            "detection_saved_search_create_error",
                            lambda details=create_details: (
                                md.create_management_saved_search(details).data.id
                            ),
                        )
            for duplicate in matches[1:]:
                duplicate_current = detection_api_call(
                    "detection_saved_search_get_error",
                    lambda search_id=duplicate.id: md.get_management_saved_search(search_id),
                )
                duplicate_etag = duplicate_current.headers.get("etag")
                detection_api_call(
                    "detection_saved_search_delete_error",
                    lambda search_id=duplicate.id, etag=duplicate_etag: (
                        md.delete_management_saved_search(
                            search_id,
                            if_match=etag,
                        )
                    ),
                )
        else:
            saved_search_id = detection_api_call(
                "detection_saved_search_create_error",
                lambda details=desired: md.create_management_saved_search(details).data.id,
            )
        planned.append(
            (
                key,
                rule,
                task_name,
                saved_search_id,
                current,
            )
        )
    created = retained = 0
    for key, rule, task_name, saved_search_id, current in planned:
        if current is not None:
            details = detection_api_call(
                "detection_scheduled_task_get_error",
                lambda task_id=current.id: la.get_scheduled_task(namespace, task_id).data,
            )
            action = details.action
            schedule = details.schedules[0]
            if (
                action.saved_search_id == saved_search_id
                and action.saved_search_duration == interval
                and schedule.recurring_interval == interval
            ):
                retained += 1
                continue
            detection_api_call(
                "detection_scheduled_task_delete_error",
                lambda task_id=current.id: la.delete_scheduled_task(namespace, task_id),
            )
        details = task_details(
            display_name=task_name,
            description=rule["description"],
            saved_search_id=saved_search_id,
            compartment_id=compartment_id,
            deployment_name=deployment_name,
            metric_name=key,
            interval=interval,
        )
        for attempt in range(retry_attempts):
            try:
                la.create_scheduled_task(namespace, details)
                created += 1
                break
            except oci.exceptions.ServiceError as exc:
                if exc.status != 400 or attempt == retry_attempts - 1:
                    raise DetectionReconciliationError(
                        _service_error_stage("detection_scheduled_task_create_error", exc)
                    ) from exc
                time.sleep(retry_delay_seconds)
    return {
        "detections": len(planned),
        "created_or_replaced": created,
        "retained": retained,
        "status": "reconciled",
    }


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
    rules = json.loads(CATALOG.read_text())
    config = oci.config.from_file(profile_name=args.profile)
    la = oci.log_analytics.LogAnalyticsClient(config)
    md = oci.management_dashboard.DashxApisClient(config)
    namespace = la.list_namespaces(config["tenancy"]).data.items[0].namespace_name
    if args.dry_run:
        existing = oci.pagination.list_call_get_all_results(
            la.list_scheduled_tasks,
            namespace,
            compartment_id=args.compartment_id,
            task_type="SAVED_SEARCH",
        ).data
        task_names = {item.display_name for item in existing}
        print(
            json.dumps(
                {
                    "detections": len(rules),
                    "existing_schedules": sum(
                        f"{args.deployment_name} - {rule['title']}" in task_names
                        for rule in rules.values()
                    ),
                    "status": "planned",
                }
            )
        )
        return 0
    result = reconcile_detections(
        log_analytics=la,
        dashboards=md,
        namespace=namespace,
        compartment_id=args.compartment_id,
        deployment_name=args.deployment_name,
        interval=args.interval,
        rules=rules,
        scope_compartment_id=args.scope_compartment_id,
        replace_searches=args.replace_searches,
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
