#!/usr/bin/env python3
"""Build deterministic OCI Management Dashboard import JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "dashboards" / "catalog.json"
QUERY_DIR = ROOT / "dashboards" / "queries"
DEFAULT_OUTPUT = ROOT / "dashboards" / "generated_bundle.json"
SUPPORTED = {"tile", "line", "bar", "hbar", "summary_table", "table"}
PLACEHOLDER_PATTERNS = ("{{", "REPLACE_ME", "GOES HERE")


def _scope_filters(compartment: str) -> dict:
    log_group_value = {
        "label": "Selected compartment",
        "value": compartment,
    }
    return {
        "LogGroup": {
            "flags": {"IncludeSubCompartments": True},
            "type": "LogGroup",
            "values": [log_group_value],
        },
        "Entity": {
            "flags": {
                "IncludeDependents": True,
                "ScopeCompartmentId": compartment,
            },
            "type": "Entity",
            "values": [],
        },
        "LogSet": {
            "flags": {},
            "type": "LogSet",
            "values": [],
        },
        "filters": [
            {
                "flags": {"includeSubCompartments": True},
                "type": "LogGroup",
                "values": [log_group_value],
            },
            {
                "flags": {
                    "includeDependents": True,
                    "scopeCompartmentId": compartment,
                },
                "type": "Entity",
                "values": [],
            },
            {
                "flags": {},
                "type": "LogSet",
                "values": [],
            },
        ],
        "isGlobal": False,
    }


def _saved_search(search_id: str, query: dict, compartment: str, period: str) -> dict:
    return {
        "id": search_id,
        "displayName": query["title"],
        "providerId": "log-analytics",
        "providerName": "Log Analytics",
        "providerVersion": "3.0.0",
        "compartmentId": compartment,
        "isOobSavedSearch": False,
        "description": query["description"],
        "nls": {},
        "type": "SEARCH_SHOW_IN_DASHBOARD",
        "uiConfig": {
            "enableWidgetInApp": True,
            "queryString": query["query"],
            # The Log Analytics widget must deserialize a complete scope
            # before dashboard parameter overrides are applied.
            "scopeFilters": _scope_filters(compartment),
            "showTitle": True,
            "timeSelection": {"timePeriod": period},
            "visualizationOptions": query.get("options", {}),
            "visualizationType": query["visualization"],
            "vizType": "lxSavedSearchWidgetType",
        },
        "dataConfig": [],
        "screenImage": " ",
        "metadataVersion": "2.0",
        # These are the current Log Analytics widget component contracts.
        # The legacy visualizations/widget pair imports successfully but the
        # OCI console fails before query execution with an Oracle JET
        # `localName` error, leaving every widget blank.
        "widgetTemplate": "visualizations/chartWidgetTemplate.html",
        "widgetVM": "jet-modules/dashboards/widgets/lxSavedSearchWidget",
        "parametersConfig": [],
        "featuresConfig": {
            "crossService": {"shared": False},
            "serviceTypes": ["log-analytics"],
        },
        "freeformTags": {
            "solution": "oci-datasafe-log-analytics",
            "visualization": query["visualization"],
        },
        "definedTags": {},
    }


def _validate_query(query_id: str, query: dict) -> None:
    required = {"title", "description", "query", "visualization", "layout"}
    missing = sorted(required - set(query))
    if missing:
        raise ValueError(f"{query_id}: missing {', '.join(missing)}")
    if query["visualization"] not in SUPPORTED:
        raise ValueError(f"{query_id}: unsupported visualization {query['visualization']}")
    text = query["query"]
    if "'Log Source' = 'OCI Data Safe Database Audit'" not in text:
        raise ValueError(f"{query_id}: missing canonical log source selector")
    if any(pattern in text for pattern in PLACEHOLDER_PATTERNS):
        raise ValueError(f"{query_id}: unresolved placeholder")
    if re.search(r":[a-zA-Z_][a-zA-Z0-9_]*", text):
        raise ValueError(f"{query_id}: runtime colon parameters are dashboard-unsafe")
    viz = query["visualization"]
    if "| timestats " in text and viz != "line":
        raise ValueError(f"{query_id}: timestats must use a line visualization")
    if viz == "line":
        options = query.get("options", {})
        if not options.get("timeField") or not options.get("valueField"):
            raise ValueError(f"{query_id}: line visualization needs timeField and valueField")
    width = int(query["layout"]["width"])
    height = int(query["layout"]["height"])
    if width < 1 or width > 12 or height < 1:
        raise ValueError(f"{query_id}: invalid layout")


def _load_query(query_id: str) -> dict:
    path = QUERY_DIR / f"{query_id}.json"
    if not path.exists():
        raise ValueError(f"missing query: {query_id}")
    query = json.loads(path.read_text())
    _validate_query(query_id, query)
    return query


def _place(queries: list[tuple[str, dict]]) -> list[dict]:
    tiles = []
    row = column = row_height = 0
    for query_id, query in queries:
        width = int(query["layout"]["width"])
        height = int(query["layout"]["height"])
        if column and column + width > 12:
            row += row_height
            column = row_height = 0
        tiles.append(
            {
                "displayName": query["title"],
                "savedSearchId": query_id,
                "row": row,
                "column": column,
                "height": height,
                "width": width,
                "nls": {},
                "uiConfig": {},
                "dataConfig": [],
                "state": "DEFAULT",
                "drilldownConfig": [],
                "parametersMap": {
                    "log-analytics-entity": ("$(dashboard.params.log-analytics-entity-filter)"),
                    "log-analytics-log-group-compartment": (
                        "$(dashboard.params.log-analytics-loggroup-filter)"
                    ),
                    "time": "$(dashboard.params.time)",
                },
            }
        )
        column += width
        row_height = max(row_height, height)
        if column == 12:
            row += row_height
            column = row_height = 0
    return tiles


def _assert_no_overlap(tiles: list[dict]) -> None:
    occupied: set[tuple[int, int]] = set()
    for tile in tiles:
        for row in range(tile["row"], tile["row"] + tile["height"]):
            for column in range(tile["column"], tile["column"] + tile["width"]):
                point = (row, column)
                if point in occupied:
                    raise ValueError(f"overlapping tile at {point}")
                occupied.add(point)


def build_bundle() -> dict:
    catalog = json.loads(CATALOG_PATH.read_text())
    compartment = "${compartment_id}"
    period = catalog["default_time_period"]
    dashboards = []
    query_inventory: dict[str, dict] = {}
    for tab in catalog["tabs"]:
        if len(tab["widgets"]) > 20:
            raise ValueError(f"{tab['id']}: OCI dashboard limit is 20 saved searches")
        queries = [(query_id, _load_query(query_id)) for query_id in tab["widgets"]]
        for query_id, query in queries:
            query_inventory[query_id] = query
        tiles = _place(queries)
        _assert_no_overlap(tiles)
        dashboards.append(
            {
                "dashboardId": f"datasafe-audit-{tab['id']}",
                "providerId": "log-analytics",
                "providerName": "Log Analytics",
                "providerVersion": "3.0.0",
                "displayName": f"Data Safe Audit | {tab['label']}",
                "description": tab["description"],
                "compartmentId": compartment,
                "isOobDashboard": False,
                "isShowInHome": True,
                "isShowDescription": True,
                "metadataVersion": "2.0",
                "type": "normal",
                "isFavorite": tab["id"] == "activity-overview",
                "nls": {},
                "uiConfig": {
                    "isFilteringEnabled": True,
                    "isRefreshEnabled": True,
                    "isTimeRangeEnabled": True,
                    "suiteName": catalog["display_name"],
                    "tabId": tab["id"],
                    "tabLabel": tab["label"],
                },
                "dataConfig": [],
                "screenImage": " ",
                "freeformTags": {
                    "solution": "oci-datasafe-log-analytics",
                    "suite": "data-safe-audit",
                    "tab": tab["id"],
                },
                "definedTags": {},
                "parametersConfig": [
                    {
                        "paramName": "log-analytics-loggroup-filter",
                        "displayName": "Log Group Compartment",
                        "paramType": "LogAnalyticsLogGroupCompartment",
                        "defaultValue": compartment,
                        "isRequired": False,
                    },
                    {
                        "paramName": "log-analytics-entity-filter",
                        "displayName": "Entity",
                        "paramType": "LogAnalyticsEntity",
                        "defaultValue": "",
                        "isRequired": False,
                    },
                    {
                        "paramName": "time",
                        "displayName": "Time Range",
                        "paramType": "Time",
                        "defaultValue": period,
                        "isRequired": False,
                    },
                ],
                "drilldownConfig": [],
                "featuresConfig": {
                    "crossService": {"shared": False},
                    "serviceTypes": ["log-analytics"],
                },
                "tiles": tiles,
                "savedSearches": [
                    _saved_search(query_id, query, compartment, period)
                    for query_id, query in queries
                ],
            }
        )
    orphaned = sorted(
        path.stem for path in QUERY_DIR.glob("*.json") if path.stem not in query_inventory
    )
    if orphaned:
        raise ValueError(f"queries not referenced by a tab: {', '.join(orphaned)}")
    return {
        "schemaVersion": "1.0",
        "suite": {
            "displayName": catalog["display_name"],
            "description": catalog["description"],
            "navigation": [
                {"id": tab["id"], "label": tab["label"], "order": index}
                for index, tab in enumerate(catalog["tabs"], start=1)
            ],
        },
        "dashboards": dashboards,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_bundle(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            raise SystemExit(f"{args.output} is stale; regenerate it")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
