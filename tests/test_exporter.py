from datetime import UTC, datetime
from types import SimpleNamespace

from oci_datasafe_exporter.config import ExportConfig
from oci_datasafe_exporter.cursor import Cursor, LoadedCursor
from oci_datasafe_exporter.exporter import AuditExporter


class FakeCursorStore:
    def __init__(self):
        self.saved = None

    def load(self, default):
        return LoadedCursor(Cursor(default, ["duplicate"]), "etag")

    def save(self, cursor, etag):
        self.saved = (cursor, etag)


class FakeDataSafe:
    def __init__(self):
        self.calls = []

    def list_audit_events(self, **kwargs):
        self.calls.append(kwargs)
        items = [
            {
                "id": "duplicate",
                "audit_event_time": "2026-07-30T11:00:00Z",
                "time_collected": "2026-07-30T11:01:00Z",
            },
            {
                "id": "new",
                "audit_event_time": "2026-07-30T11:02:00Z",
                "time_collected": "2026-07-30T11:03:00Z",
                "operation": "SELECT",
            },
        ]
        return SimpleNamespace(data=SimpleNamespace(items=items), headers={})


class FakeLogging:
    def __init__(self):
        self.calls = []

    def put_logs(self, log_id, details):
        self.calls.append((log_id, details))


def test_exporter_uses_scim_cursor_deduplicates_and_advances_after_logging():
    config = ExportConfig(
        data_safe_compartment_id="compartment",
        logging_log_id="log",
        cursor_bucket_name="bucket",
        hash_client_ip=False,
    )
    store = FakeCursorStore()
    data_safe = FakeDataSafe()
    logging = FakeLogging()
    exporter = AuditExporter(
        config,
        data_safe,
        logging,
        store,
        now=lambda: datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
    )
    result = exporter.run()
    assert "timeCollected gt" in data_safe.calls[0]["scim_query"]
    assert result.queried == 2
    assert result.exported == 1
    assert result.duplicates == 1
    assert len(logging.calls) == 1
    assert store.saved[1] == "etag"
    assert "new" in store.saved[0].recent_event_ids
