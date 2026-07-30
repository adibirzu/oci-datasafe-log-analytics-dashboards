"""Durable cursor storage with optimistic concurrency."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import oci


@dataclass
class Cursor:
    high_watermark: str
    recent_event_ids: list[str] = field(default_factory=list)
    schema_version: int = 1

    def to_json(self) -> str:
        return json.dumps(
            {
                "schemaVersion": self.schema_version,
                "highWatermark": self.high_watermark,
                "recentEventIds": self.recent_event_ids[-5000:],
                "updatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class LoadedCursor:
    cursor: Cursor
    etag: str | None


class CursorConflict(RuntimeError):
    """Another invocation advanced the cursor."""


class ObjectStorageCursorStore:
    def __init__(self, client: Any, namespace: str, bucket: str, object_name: str):
        self.client = client
        self.namespace = namespace
        self.bucket = bucket
        self.object_name = object_name

    def load(self, default_high_watermark: str) -> LoadedCursor:
        try:
            response = self.client.get_object(self.namespace, self.bucket, self.object_name)
        except oci.exceptions.ServiceError as exc:
            if exc.status == 404:
                return LoadedCursor(Cursor(default_high_watermark), None)
            raise
        payload = json.loads(response.data.text)
        return LoadedCursor(
            Cursor(
                high_watermark=payload["highWatermark"],
                recent_event_ids=list(payload.get("recentEventIds", [])),
                schema_version=int(payload.get("schemaVersion", 1)),
            ),
            response.headers.get("etag"),
        )

    def save(self, cursor: Cursor, etag: str | None) -> None:
        kwargs = {"if_match": etag} if etag else {"if_none_match": "*"}
        try:
            self.client.put_object(
                self.namespace,
                self.bucket,
                self.object_name,
                cursor.to_json().encode(),
                content_type="application/json",
                **kwargs,
            )
        except oci.exceptions.ServiceError as exc:
            if exc.status in {409, 412}:
                raise CursorConflict("cursor was updated by another invocation") from exc
            raise
