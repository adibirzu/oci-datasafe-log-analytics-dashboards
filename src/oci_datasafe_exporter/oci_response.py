"""Safe decoding helpers for OCI SDK streaming responses."""

from __future__ import annotations

from typing import Any


def response_bytes(payload: Any) -> bytes:
    """Return bytes from an OCI SDK response payload without stringifying it.

    Functions invocation and content-export APIs use a streaming HTTP response.
    Its body is exposed as ``data`` by urllib3, rather than supporting
    ``bytes(response)``. Other OCI SDK operations may expose ``content`` or
    raw bytes directly, so accept each documented transport shape.
    """
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, bytearray):
        return bytes(payload)
    for attribute in ("content", "data"):
        value = getattr(payload, attribute, None)
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
    raise TypeError("OCI response did not contain a byte payload")
