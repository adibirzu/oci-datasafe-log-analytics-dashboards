#!/usr/bin/env python3
"""Build a deterministic, secret-free OCI Resource Manager stack ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "terraform"
DEFAULT_OUTPUT = ROOT / "dist" / "oci-datasafe-log-analytics-stack.zip"
FORBIDDEN_NAMES = {".terraform", "terraform.tfvars"}
FORBIDDEN_SUFFIXES = {".tfstate", ".plan"}
SECRET_PATTERNS = (
    re.compile(rb"ocid1\.[a-z0-9.-]+\.\.[a-z0-9]+"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def package_files() -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in sorted(TERRAFORM.glob("*.tf")):
        files[path.name] = path.read_bytes()
    for name in ("schema.yaml", ".terraform.lock.hcl"):
        files[name] = (TERRAFORM / name).read_bytes()
    files["content/oci-datasafe-log-analytics-content.zip"] = (
        TERRAFORM / "content" / "oci-datasafe-log-analytics-content.zip"
    ).read_bytes()
    files["dashboard_bundle.json"] = (
        ROOT / "dashboards" / "generated_bundle.json"
    ).read_bytes()
    return files


def validate(files: dict[str, bytes]) -> None:
    if "schema.yaml" not in files or "main.tf" not in files:
        raise RuntimeError("Resource Manager package is missing its root configuration")
    for name, content in files.items():
        parts = set(Path(name).parts)
        if parts & FORBIDDEN_NAMES or Path(name).suffix in FORBIDDEN_SUFFIXES:
            raise RuntimeError(f"forbidden package entry: {name}")
        if name.endswith(".zip"):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                raise RuntimeError(f"tenancy-specific or secret content in {name}")
    content_zip = files["content/oci-datasafe-log-analytics-content.zip"]
    with zipfile.ZipFile(io.BytesIO(content_zip)) as archive:
        xml = archive.read("content.xml")
        if b"ocid1." in xml:
            raise RuntimeError("portable Log Analytics content contains an OCID")


def build(output: Path) -> str:
    files = package_files()
    validate(files)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    digest = build(args.output)
    print(f"wrote {args.output} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
