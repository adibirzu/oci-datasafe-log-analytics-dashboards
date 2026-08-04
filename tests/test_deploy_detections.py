from types import SimpleNamespace

from scripts import deploy_detections
from scripts.deploy_detections import (
    DetectionReconciliationError,
    detection_api_call,
    reconcile_detections,
    saved_search_details,
    saved_search_is_current,
    task_details,
)


def test_scheduled_detection_supplies_duration_and_metric_contract():
    details = task_details(
        display_name="customer-deploy - Failed Login Spike",
        description="Repeated failures.",
        saved_search_id="ocid1.managementsavedsearch.oc1..example",
        compartment_id="ocid1.compartment.oc1..example",
        deployment_name="customer-deploy",
        metric_name="failed_login_spike",
        interval="PT5M",
    )
    assert details.action.saved_search_duration == "PT5M"
    assert details.action.metric_extraction.namespace == "datasafe_audit"
    assert details.action.metric_extraction.metric_name == "failed_login_spike"
    assert getattr(details.schedules[0], "query_offset_secs", 120) == 120


def test_saved_search_is_service_shared_and_uses_runtime_log_group():
    details = saved_search_details(
        display_name="customer-deploy | Failed Login Spike",
        description="Repeated failures.",
        compartment_id="ocid1.compartment.oc1..example",
        scope_compartment_id="ocid1.compartment.oc1..example",
        query="* | stats count as DetectionCount",
    )
    assert details.features_config["crossService"]["shared"] is True
    assert (
        details.ui_config["scopeFilters"]["LogGroup"]["values"][0]["value"]
        == "ocid1.compartment.oc1..example"
    )
    assert details.ui_config["scopeFilters"]["Entity"]["values"] == []
    assert details.ui_config["scopeFilters"]["LogSet"]["values"] == []
    assert len(details.ui_config["scopeFilters"]["filters"]) == 3


def test_saved_search_current_comparison_ignores_service_metadata():
    desired = saved_search_details(
        display_name="customer-deploy | Failed Login Spike",
        description="Repeated failures.",
        compartment_id="ocid1.compartment.oc1..example",
        scope_compartment_id="ocid1.compartment.oc1..example",
        query="* | stats count as DetectionCount",
        update=True,
    )
    current = SimpleNamespace(
        **{
            field: getattr(desired, field)
            for field in (
                "display_name",
                "description",
                "provider_id",
                "provider_name",
                "provider_version",
                "type",
                "ui_config",
                "freeform_tags",
            )
        },
        id="service-generated-id",
        time_updated="service-generated-time",
    )
    assert saved_search_is_current(current, desired)
    current.description = "drifted"
    assert not saved_search_is_current(current, desired)


def test_reconcile_is_resource_principal_compatible_and_idempotent_on_empty_inventory(
    monkeypatch,
):
    created_searches = []
    created_tasks = []

    class Dashboards:
        def list_management_saved_searches(self, **_kwargs):
            return None

        def create_management_saved_search(self, details):
            created_searches.append(details)
            return SimpleNamespace(data=SimpleNamespace(id=f"search-{len(created_searches)}"))

    class LogAnalytics:
        def list_scheduled_tasks(self, *_args, **_kwargs):
            return None

        def create_scheduled_task(self, _namespace, details):
            created_tasks.append(details)

    monkeypatch.setattr(
        deploy_detections.oci.pagination,
        "list_call_get_all_results",
        lambda _method, *_args, **_kwargs: SimpleNamespace(data=[]),
    )
    result = reconcile_detections(
        log_analytics=LogAnalytics(),
        dashboards=Dashboards(),
        namespace="namespace",
        compartment_id="compartment",
        deployment_name="demo",
        interval="PT5M",
        rules={
            "failed_login": {
                "title": "Failed Login",
                "description": "Repeated failures.",
                "query": "* | stats count as DetectionCount",
            }
        },
        retry_attempts=1,
    )
    assert result == {
        "detections": 1,
        "created_or_replaced": 1,
        "retained": 0,
        "status": "reconciled",
    }
    assert created_searches[0].display_name == "demo | Failed Login"
    assert created_tasks[0].action.saved_search_duration == "PT5M"


def test_detection_api_call_exposes_only_a_stable_operation_and_status():
    def fail():
        raise deploy_detections.oci.exceptions.ServiceError(
            status=403,
            code="NotAuthorized",
            headers={},
            message="tenant-specific detail",
        )

    with __import__("pytest").raises(DetectionReconciliationError) as error:
        detection_api_call("detection_saved_search_list_error", fail)
    assert error.value.stage == "detection_saved_search_list_authorization_error"
    assert "tenant-specific" not in str(error.value)


def test_detection_api_call_classifies_validation_without_reflecting_payload():
    def fail():
        raise deploy_detections.oci.exceptions.ServiceError(
            status=400,
            code="InvalidParameter",
            headers={},
            message="tenant-specific detail",
        )

    with __import__("pytest").raises(DetectionReconciliationError) as error:
        detection_api_call("detection_saved_search_update_error", fail)
    assert error.value.stage == "detection_saved_search_update_validation_error"
    assert "tenant-specific" not in str(error.value)
