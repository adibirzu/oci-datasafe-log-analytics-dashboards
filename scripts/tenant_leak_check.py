#!/usr/bin/env python3
"""Fail when deployable repository content contains tenant-specific literals."""

from __future__ import annotations

import argparse
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED_PREFIXES = ("tests/", ".git/", "evidence/")
IGNORED_FILES = {"scripts/tenant_leak_check.py"}
PATTERNS = {
    "literal_ocid": re.compile(r"ocid1\.[a-z0-9-]+\.[a-z0-9-]*\.[a-z0-9-]*\.[A-Za-z0-9._-]{20,}"),
    "public_or_private_ipv4": re.compile(r"(?<![\w<])(?:\d{1,3}\.){3}\d{1,3}(?![\w>])"),
    "internal_profile": re.compile(
        r"(?i)(?:profile|OCI_PROFILE)[^\n]{0,30}(?:=|default|:-)\s*[\"']?cap\b"
    ),
    "internal_region": re.compile(r"\beu-frankfurt-1\b"),
    "synthetic_runtime_record": re.compile(r"synthetic-(?:cap|e2e)", re.IGNORECASE),
}


def tracked_files() -> list[Path]:
    output = subprocess.run(  # noqa: S603
        ["/usr/bin/git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return [ROOT / item.decode() for item in output.split(b"\0") if item]


def scan_text(label: str, text: str) -> list[str]:
    findings = []
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            if name == "public_or_private_ipv4":
                context = text[max(0, match.start() - 24) : match.start()]
                if re.search(r"(?:oms_|content_)?version=[\"']$", context):
                    continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{label}:{line}: {name}")
    return findings


def scan_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    relative = path.relative_to(ROOT).as_posix()
    if relative in IGNORED_FILES or relative.startswith(IGNORED_PREFIXES):
        return []
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".pyc"}:
        return []
    if path.suffix.lower() == ".zip":
        findings = []
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                try:
                    text = archive.read(name).decode()
                except UnicodeDecodeError:
                    continue
                findings.extend(scan_text(f"{relative}!{name}", text))
        return findings
    try:
        return scan_text(relative, path.read_text())
    except UnicodeDecodeError:
        return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--extra-deny",
        action="append",
        default=[],
        help="Additional exact tenant value to reject; repeat as needed.",
    )
    args = parser.parse_args()
    findings = []
    for path in tracked_files():
        findings.extend(scan_file(path))
        if args.extra_deny and path.is_file() and path.suffix.lower() != ".zip":
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            for value in args.extra_deny:
                if value and value in text:
                    findings.append(f"{path.relative_to(ROOT)}: customer deny value")
    if findings:
        print("\n".join(sorted(findings)))
        return 1
    print("tenant-leak-check: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
