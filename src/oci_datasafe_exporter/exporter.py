"""Bounded, resumable Data Safe to OCI Logging export pipeline."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import oci

from .config import ExportConfig
from .cursor import Cursor, ObjectStorageCursorStore
from .normalize import event_id, normalize_event

LOG = logging.getLogger(__name__)

CLASSIFIERS = {
    "admin_user": "adminUser",
    "common_user": "commonUser",
    "sensitive_activity": "sensitiveActivity",
    "ds_activity": "dsActivity",
}


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


@dataclass(frozen=True)
class ExportResult:
    queried: int
    exported: int
    duplicates: int
    batches: int
    high_watermark: str
    truncated: bool


class AuditExporter:
    def __init__(
        self,
        config: ExportConfig,
        data_safe_client: Any,
        logging_client: Any,
        cursor_store: ObjectStorageCursorStore,
        now: Any | None = None,
    ):
        self.config = config
        self.data_safe = data_safe_client
        self.logging = logging_client
        self.cursor_store = cursor_store
        self.now = now or (lambda: datetime.now(UTC))

    def _window(self) -> tuple[str, str, Any]:
        end = self.now() - timedelta(seconds=self.config.safety_lag_seconds)
        default = end - timedelta(minutes=self.config.initial_lookback_minutes)
        loaded = self.cursor_store.load(_rfc3339(default))
        start = _parse_time(loaded.cursor.high_watermark) - timedelta(
            minutes=self.config.overlap_minutes
        )
        return _rfc3339(start), _rfc3339(end), loaded

    def _list_events(
        self,
        start: str,
        end: str,
        extra_filter: str | None = None,
        max_events: int | None = None,
    ) -> tuple[list[Any], bool]:
        scim_query = f'(timeCollected gt "{start}") and (timeCollected le "{end}")'
        if extra_filter:
            scim_query = f"({scim_query}) and ({extra_filter})"
        items: list[Any] = []
        page = None
        truncated = False
        limit_total = max_events or self.config.max_events
        while True:
            response = self.data_safe.list_audit_events(
                compartment_id=self.config.data_safe_compartment_id,
                compartment_id_in_subtree=self.config.include_subcompartments,
                access_level="ACCESSIBLE",
                scim_query=scim_query,
                sort_by="timeCollected",
                sort_order="ASC",
                limit=self.config.page_size,
                page=page,
            )
            remaining = limit_total - len(items)
            items.extend(response.data.items[:remaining])
            next_page = response.headers.get("opc-next-page")
            if len(items) >= limit_total:
                truncated = bool(next_page) or len(response.data.items) > remaining
                break
            if not next_page:
                break
            page = next_page
        return items, truncated

    def _classifier_event_ids(self, start: str, end: str) -> dict[str, set[str]]:
        """Fetch Data Safe's filter-only report classifiers and join by event id."""
        classified: dict[str, set[str]] = {}
        for wire_name, filter_name in CLASSIFIERS.items():
            items, _ = self._list_events(
                start,
                end,
                f"{filter_name} eq 1",
                self.config.max_events,
            )
            classified[wire_name] = {
                str(oci.util.to_dict(item).get("id"))
                for item in items
                if oci.util.to_dict(item).get("id")
            }
        return classified

    def _batches(self, events: Iterable[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
        batch: list[dict[str, Any]] = []
        size = 0
        for event in events:
            encoded_size = len(json.dumps(event, separators=(",", ":")).encode())
            if batch and (
                len(batch) >= self.config.max_batch_entries
                or size + encoded_size > self.config.max_batch_bytes
            ):
                yield batch
                batch = []
                size = 0
            batch.append(event)
            size += encoded_size
        if batch:
            yield batch

    def _put_batch(self, batch: list[dict[str, Any]]) -> None:
        entries = []
        for item in batch:
            timestamp = item.get("audit_event_time") or item.get("time_collected")
            entries.append(
                oci.loggingingestion.models.LogEntry(
                    data=json.dumps(item, separators=(",", ":")),
                    id=event_id(item),
                    time=timestamp,
                )
            )
        details = oci.loggingingestion.models.PutLogsDetails(
            specversion="1.0",
            log_entry_batches=[
                oci.loggingingestion.models.LogEntryBatch(
                    entries=entries,
                    source="OCIDataSafe",
                    type="com.oraclecloud.logging.custom.datasafe.audit",
                    subject="OracleDatabaseAudit",
                    defaultlogentrytime=_rfc3339(self.now()),
                )
            ],
        )
        self.logging.put_logs(self.config.logging_log_id, details)

    def run(self, export_run_id: str | None = None) -> ExportResult:
        start, end, loaded = self._window()
        raw_events, truncated = self._list_events(start, end)
        classifier_end = end
        if truncated and raw_events:
            classifier_end = str(
                oci.util.to_dict(raw_events[-1]).get("time_collected") or end
            )
        classified = self._classifier_event_ids(start, classifier_end)
        seen = set(loaded.cursor.recent_event_ids)
        normalized: list[dict[str, Any]] = []
        duplicates = 0
        for raw in raw_events:
            enriched = oci.util.to_dict(raw)
            raw_id = str(enriched.get("id") or "")
            for wire_name, ids in classified.items():
                enriched[wire_name] = 1 if raw_id in ids else 0
            item = normalize_event(enriched, self.config)
            if export_run_id:
                item["export_run_id"] = export_run_id
            if event_id(item) in seen:
                duplicates += 1
                continue
            normalized.append(item)
            seen.add(event_id(item))

        batches = 0
        for batch in self._batches(normalized):
            self._put_batch(batch)
            batches += 1

        if truncated and normalized:
            high_watermark = str(normalized[-1].get("time_collected") or end)
        else:
            high_watermark = end
        recent_ids = (loaded.cursor.recent_event_ids + [event_id(x) for x in normalized])[-5000:]
        self.cursor_store.save(Cursor(high_watermark, recent_ids), loaded.etag)
        return ExportResult(
            queried=len(raw_events),
            exported=len(normalized),
            duplicates=duplicates,
            batches=batches,
            high_watermark=high_watermark,
            truncated=truncated,
        )
