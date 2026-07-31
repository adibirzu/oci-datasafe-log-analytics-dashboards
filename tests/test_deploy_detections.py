from scripts.deploy_detections import saved_search_details, task_details


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
        log_group_id="ocid1.loganalyticsloggroup.oc1..example",
        query="* | stats count as DetectionCount",
    )
    assert details.features_config["crossService"]["shared"] is True
    assert (
        details.ui_config["scopeFilters"]["LogGroup"]["values"][0]["value"]
        == "ocid1.loganalyticsloggroup.oc1..example"
    )
