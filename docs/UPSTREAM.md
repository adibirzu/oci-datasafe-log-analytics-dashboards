# Upstream baseline

The implementation starts from Oracle DevRel's **Data Safe Audit Database to OCI
Logging** reference architecture.

- Repository: `oracle-devrel/technology-engineering`
- Path: `oci-and-db/foundation/ciso/security-design/shared-assets/fn-datasafe-dbaudit-to-oci-logging`
- Inspected revision: `45f688b90e14326dde75aaa117756917e63f7aba`
- Inspection date: 2026-07-30
- License: UPL-1.0

## Reused ideas

- Data Safe `list_audit_events` as the audit source.
- OCI Functions resource principals.
- OCI Logging ingestion batches.
- Object Storage for durable cursor state.

## Replaced or extended

- Removed the pandas dependency from the function image.
- Uses a collision-safe cursor with overlap and event-ID deduplication.
- Uses OCI Resource Scheduler instead of a permanently firing Monitoring alarm.
- Routes OCI Logging to Log Analytics through Connector Hub.
- Provisions the Log Analytics JSON field/parser/source contract.
- Generates and validates a multi-dashboard set that recreates Data Safe
  Activity Auditing and Audit Insights views.
- Adds local, live parser, ingestion, dashboard, detection, and E2E gates.
