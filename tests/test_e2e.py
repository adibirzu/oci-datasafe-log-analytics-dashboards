import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("e2e", ROOT / "scripts" / "e2e.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_aggregate_count_rejects_zero_value_row_as_evidence():
    assert MODULE.aggregate_count([{"Events": 0}]) == 0
    assert MODULE.aggregate_count([{"Events": "0"}]) == 0
    assert MODULE.aggregate_count([]) == 0


def test_aggregate_count_accepts_positive_source_evidence():
    assert MODULE.aggregate_count([{"Events": 6413}]) == 6413
