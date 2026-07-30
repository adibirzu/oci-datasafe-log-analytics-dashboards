#!/usr/bin/env python3
"""Export the live, validated Data Safe Log Analytics contract as a portable ZIP."""

from __future__ import annotations

import argparse
import io
import re
import zipfile
from pathlib import Path

import oci
from oci.log_analytics.models import ExportContent
from setup_log_analytics_content import (
    PARSER_NAME,
    SOURCE_DISPLAY,
    SOURCE_INTERNAL,
    existing_fields,
    namespace_for,
)

from oci_datasafe_exporter.normalize import FIELD_ALIASES


def _portable_zip(payload: bytes) -> bytes:
    """Remove tenancy identity from the export and make the ZIP reproducible."""
    source = zipfile.ZipFile(io.BytesIO(payload))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name in sorted(source.namelist()):
            content = source.read(name)
            if name == "content.xml":
                text = content.decode("utf-8")
                text = re.sub(
                    r'name="content_ocid1\.tenancy\.[^"]+"',
                    'name="oci_datasafe_log_analytics_content"',
                    text,
                    count=1,
                )
                content = text.encode("utf-8")
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            target.writestr(info, content)
    return output.getvalue()


def _source_name(client, namespace: str, compartment_id: str) -> str:
    response = oci.pagination.list_call_get_all_results(
        client.list_sources,
        namespace,
        compartment_id,
        is_system="ALL",
    )
    matches = [
        source
        for source in response.data
        if source.name in {SOURCE_INTERNAL, SOURCE_DISPLAY}
        or source.display_name == SOURCE_DISPLAY
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one {SOURCE_DISPLAY!r} source, found {len(matches)}"
        )
    return matches[0].name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="cap")
    parser.add_argument("--compartment-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("terraform/content/oci-datasafe-log-analytics-content.zip"),
    )
    args = parser.parse_args()

    config = oci.config.from_file(profile_name=args.profile)
    client = oci.log_analytics.LogAnalyticsClient(config)
    namespace = namespace_for(client, config["tenancy"])
    fields = existing_fields(client, namespace)
    display_names = list(FIELD_ALIASES.values()) + ["Schema Version"]
    missing = sorted(set(display_names) - set(fields))
    if missing:
        raise RuntimeError(f"missing Log Analytics fields: {', '.join(missing)}")
    details = ExportContent(
        parser_names=[PARSER_NAME],
        source_names=[_source_name(client, namespace, args.compartment_id)],
    )
    response = client.export_custom_content(namespace, details)
    payload = response.data.content if hasattr(response.data, "content") else response.data
    if not isinstance(payload, bytes) or not payload.startswith(b"PK"):
        raise RuntimeError("Log Analytics export did not return a ZIP payload")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_portable_zip(payload))
    print(
        f"exported {len(display_names)} fields, one parser, and one source "
        f"to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
