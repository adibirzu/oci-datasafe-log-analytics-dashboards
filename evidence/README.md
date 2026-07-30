# Evidence

Live validation writes redacted, machine-readable receipts to `evidence/live/`.
That directory is intentionally ignored because OCI resource identifiers and
tenant data must not be committed.

Repository-local test output and example receipt schemas may be committed under
`docs/`. A green local gate does not imply that a live deployment exists.
