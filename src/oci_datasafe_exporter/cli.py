"""Local profile-backed invocation for operator testing."""

from __future__ import annotations

import argparse
import json

from .config import ExportConfig
from .cursor import ObjectStorageCursorStore
from .exporter import AuditExporter
from .runtime import profile_clients


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="cap")
    args = parser.parse_args()
    config = ExportConfig.from_env()
    data_safe, logging_client, object_storage, namespace = profile_clients(args.profile)
    store = ObjectStorageCursorStore(
        object_storage,
        namespace,
        config.cursor_bucket_name,
        config.cursor_object_name,
    )
    result = AuditExporter(config, data_safe, logging_client, store).run()
    print(
        json.dumps(
            {
                "queried": result.queried,
                "exported": result.exported,
                "duplicates": result.duplicates,
                "batches": result.batches,
                "truncated": result.truncated,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
