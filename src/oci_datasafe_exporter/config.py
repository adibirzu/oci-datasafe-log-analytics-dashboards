"""Runtime configuration with fail-closed validation."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    if raw.lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _positive_int(name: str, default: int, maximum: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


@dataclass(frozen=True)
class ExportConfig:
    data_safe_compartment_id: str
    logging_log_id: str
    cursor_bucket_name: str
    cursor_object_name: str = "datasafe-audit-export/cursor.json"
    initial_lookback_minutes: int = 60
    overlap_minutes: int = 5
    safety_lag_seconds: int = 120
    page_size: int = 1000
    max_events: int = 50_000
    max_batch_entries: int = 1000
    max_batch_bytes: int = 900_000
    include_subcompartments: bool = True
    include_sql_text: bool = False
    include_command_parameters: bool = False
    hash_client_ip: bool = True
    client_ip_hash_salt: str = ""
    reconcile_detections: bool = False
    log_analytics_namespace: str = ""
    solution_compartment_id: str = ""
    deployment_name: str = ""
    detection_interval: str = "PT5M"

    @classmethod
    def from_env(cls) -> ExportConfig:
        required = {
            "DATA_SAFE_COMPARTMENT_ID": os.getenv("DATA_SAFE_COMPARTMENT_ID", ""),
            "LOGGING_LOG_ID": os.getenv("LOGGING_LOG_ID", ""),
            "CURSOR_BUCKET_NAME": os.getenv("CURSOR_BUCKET_NAME", ""),
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"missing required configuration: {', '.join(missing)}")

        hash_client_ip = _bool("HASH_CLIENT_IP", True)
        salt = os.getenv("CLIENT_IP_HASH_SALT", "")
        if hash_client_ip and len(salt) < 16:
            raise ValueError("CLIENT_IP_HASH_SALT must contain at least 16 characters")

        reconcile_detections = _bool("RECONCILE_DETECTIONS", False)
        detection_config = {
            "LOG_ANALYTICS_NAMESPACE": os.getenv("LOG_ANALYTICS_NAMESPACE", ""),
            "SOLUTION_COMPARTMENT_ID": os.getenv("SOLUTION_COMPARTMENT_ID", ""),
            "DEPLOYMENT_NAME": os.getenv("DEPLOYMENT_NAME", ""),
        }
        if reconcile_detections:
            missing_detection = [
                name for name, value in detection_config.items() if not value.strip()
            ]
            if missing_detection:
                raise ValueError(
                    "missing detection reconciliation configuration: "
                    + ", ".join(missing_detection)
                )

        return cls(
            data_safe_compartment_id=required["DATA_SAFE_COMPARTMENT_ID"],
            logging_log_id=required["LOGGING_LOG_ID"],
            cursor_bucket_name=required["CURSOR_BUCKET_NAME"],
            cursor_object_name=os.getenv("CURSOR_OBJECT_NAME", "datasafe-audit-export/cursor.json"),
            initial_lookback_minutes=_positive_int("INITIAL_LOOKBACK_MINUTES", 60, 10_080),
            overlap_minutes=_positive_int("CURSOR_OVERLAP_MINUTES", 5, 60),
            safety_lag_seconds=_positive_int("SAFETY_LAG_SECONDS", 120, 3600),
            page_size=_positive_int("DATA_SAFE_PAGE_SIZE", 1000, 1000),
            max_events=_positive_int("MAX_EVENTS_PER_RUN", 50_000, 1_000_000),
            max_batch_entries=_positive_int("MAX_BATCH_ENTRIES", 1000, 10_000),
            max_batch_bytes=_positive_int("MAX_BATCH_BYTES", 900_000, 1_000_000),
            include_subcompartments=_bool("INCLUDE_SUBCOMPARTMENTS", True),
            include_sql_text=_bool("INCLUDE_SQL_TEXT", False),
            include_command_parameters=_bool("INCLUDE_COMMAND_PARAMETERS", False),
            hash_client_ip=hash_client_ip,
            client_ip_hash_salt=salt,
            reconcile_detections=reconcile_detections,
            log_analytics_namespace=detection_config["LOG_ANALYTICS_NAMESPACE"],
            solution_compartment_id=detection_config["SOLUTION_COMPARTMENT_ID"],
            deployment_name=detection_config["DEPLOYMENT_NAME"],
            detection_interval=os.getenv("DETECTION_INTERVAL", "PT5M"),
        )
