import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_dashboard_bundle", ROOT / "scripts" / "build_dashboard_bundle.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_dashboard_suite_recreates_data_safe_landing_and_insights():
    bundle = MODULE.build_bundle()
    assert len(bundle["dashboards"]) == 8
    labels = [item["label"] for item in bundle["suite"]["navigation"]]
    assert labels == [
        "Activity Overview",
        "Predefined Reports",
        "Audit Insights",
        "Identity & Access",
        "Data & Schema",
        "Client & Network",
        "Investigation",
        "Detection & Baseline",
    ]
    titles = {
        tile["displayName"] for dashboard in bundle["dashboards"] for tile in dashboard["tiles"]
    }
    assert {"Failed Login Activity", "Admin Activity", "All Activity"} <= titles
    assert {"Events Summary", "Targets Summary"} <= titles
    assert {"Top Targets by Audit Volume", "Top Audit Policies by Volume"} <= titles
    assert {
        "Audit Policy Changes Report",
        "Database Vault Activity Report",
        "SQL Firewall Audited Violations Report",
    } <= titles
    assert {"Failed Login Detections", "Privilege & Entitlement Changes"} <= titles


def test_all_tiles_are_in_bounds_and_non_overlapping():
    for dashboard in MODULE.build_bundle()["dashboards"]:
        occupied = set()
        for tile in dashboard["tiles"]:
            assert 0 <= tile["column"] < 12
            assert tile["column"] + tile["width"] <= 12
            for row in range(tile["row"], tile["row"] + tile["height"]):
                for column in range(tile["column"], tile["column"] + tile["width"]):
                    assert (row, column) not in occupied
                    occupied.add((row, column))


def test_committed_bundle_is_current():
    expected = json.dumps(MODULE.build_bundle(), indent=2, sort_keys=True) + "\n"
    assert (ROOT / "dashboards" / "generated_bundle.json").read_text() == expected


def test_dashboard_scope_uses_runtime_parameters_not_invalid_log_group_ocids():
    for dashboard in MODULE.build_bundle()["dashboards"]:
        parameters = {
            item["paramName"]: item for item in dashboard["parametersConfig"]
        }
        assert parameters["log-analytics-loggroup-filter"]["defaultValue"] == (
            "${compartment_id}"
        )
        assert parameters["time"]["defaultValue"] == "l7d"
        assert "log-analytics-entity-filter" in parameters
        for saved_search in dashboard["savedSearches"]:
            assert saved_search["uiConfig"]["scopeFilters"] == {}
        for tile in dashboard["tiles"]:
            assert tile["parametersMap"]["log-analytics-entity"] == (
                "$(dashboard.params.log-analytics-entity-filter)"
            )
