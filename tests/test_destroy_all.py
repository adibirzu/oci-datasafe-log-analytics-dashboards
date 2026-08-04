from scripts.destroy_all import dashboard_names


def test_destroy_scope_is_exactly_catalog_dashboards():
    names = dashboard_names()
    assert "Data Safe Audit | Activity Overview" in names
    assert "Data Safe Audit | Detection & Baseline" in names
    assert len(names) == 8
