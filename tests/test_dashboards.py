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
    assert len(bundle["dashboards"]) == 6
    labels = [item["label"] for item in bundle["suite"]["navigation"]]
    assert labels == [
        "Activity Overview",
        "Audit Insights",
        "Identity & Access",
        "Data & Schema",
        "Client & Network",
        "Investigation",
    ]
    titles = {
        tile["displayName"] for dashboard in bundle["dashboards"] for tile in dashboard["tiles"]
    }
    assert {"Failed Login Activity", "Admin Activity", "All Activity"} <= titles
    assert {"Events Summary", "Targets Summary"} <= titles
    assert {"Top Targets by Audit Volume", "Top Audit Policies by Volume"} <= titles


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
