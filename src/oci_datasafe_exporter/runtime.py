"""OCI client construction for Functions resource principals or local profiles."""

from __future__ import annotations

from typing import Any

import oci


def resource_principal_clients() -> tuple[Any, Any, Any, str]:
    signer = oci.auth.signers.get_resource_principals_signer()
    object_storage = oci.object_storage.ObjectStorageClient({}, signer=signer)
    namespace = object_storage.get_namespace().data
    return (
        oci.data_safe.DataSafeClient({}, signer=signer),
        oci.loggingingestion.LoggingClient({}, signer=signer),
        object_storage,
        namespace,
    )


def resource_principal_detection_clients() -> tuple[Any, Any]:
    """Build only the clients needed to reconcile managed detections."""
    signer = oci.auth.signers.get_resource_principals_signer()
    return (
        oci.log_analytics.LogAnalyticsClient({}, signer=signer),
        oci.management_dashboard.DashxApisClient({}, signer=signer),
    )


def profile_clients(profile: str) -> tuple[Any, Any, Any, str]:
    config = oci.config.from_file(profile_name=profile)
    object_storage = oci.object_storage.ObjectStorageClient(config)
    namespace = object_storage.get_namespace().data
    return (
        oci.data_safe.DataSafeClient(config),
        oci.loggingingestion.LoggingClient(config),
        object_storage,
        namespace,
    )
