import io

from oci_datasafe_exporter.handler import _error_reason, _export_run_id


def test_e2e_marker_accepts_only_generated_opaque_value():
    marker = "a" * 32
    assert _export_run_id(io.BytesIO(f'{{"export_run_id":"{marker}"}}'.encode())) == marker
    assert _export_run_id(io.BytesIO(b'{"export_run_id":"not-a-marker"}')) is None
    assert _export_run_id(io.BytesIO(b"not-json")) is None
    assert _export_run_id(None) is None


def test_error_reason_does_not_reflect_service_error_details():
    error = _error_reason(
        __import__("oci").exceptions.ServiceError(
            status=400,
            code="InvalidParameter",
            headers={},
            message="tenant-specific detail",
        )
    )
    assert error == "oci_service_error"
    assert _error_reason(ValueError("secret configuration detail")) == "configuration_error"
    assert _error_reason(RuntimeError("internal detail")) == "runtime_error"


def test_error_reason_classifies_only_known_service_families():
    error = __import__("oci").exceptions.ServiceError(
        status=400,
        code="InvalidParameter",
        headers={},
        message="tenant-specific detail",
        target_service="data_safe",
    )
    assert _error_reason(error) == "data_safe_service_error"


def test_error_reason_preserves_only_a_stable_detection_stage():
    error = type(
        "DetectionError",
        (RuntimeError,),
        {"stage": "detection_saved_search_list_error"},
    )()
    assert _error_reason(error) == "detection_saved_search_list_error"


def test_error_reason_preserves_redacted_detection_status_category():
    error = type(
        "DetectionError",
        (RuntimeError,),
        {"stage": "detection_saved_search_update_validation_error"},
    )()
    assert _error_reason(error) == "detection_saved_search_update_validation_error"
