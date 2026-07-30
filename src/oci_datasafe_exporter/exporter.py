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

    def _list_events(self, start: str, end: str) -> tuple[list[Any], bool]:
        scim_query = f'(timeCollected gt "{start}") and (timeCollected le "{end}")'
        items: list[Any] = []
        page = None
        truncated = False
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
            remaining = self.config.max_events - len(items)
            items.extend(response.data.items[:remaining])
            next_page = response.headers.get("opc-next-page")
            if len(items) >= self.config.max_events:
                truncated = bool(next_page) or len(response.data.items) > remaining
                break
            if not next_page:
                break
            page = next_page
        return items, truncated

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

    def run(self) -> ExportResult:
        start, end, loaded = self._window()
        raw_events, truncated = self._list_events(start, end)
        seen = set(loaded.cursor.recent_event_ids)
        normalized: list[dict[str, Any]] = []
        duplicates = 0
        for raw in raw_events:
            item = normalize_event(raw, self.config)
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
