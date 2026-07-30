# Architecture and delivery boundaries

## Data path

1. Data Safe collects unified database audit records into its regional
   repository.
2. Resource Scheduler invokes the exporter function every twelve hours by
   default, with one-hour, six-hour, one-day, and custom cadence options.
3. The function reads a bounded `timeCollected` SCIM window. The window
   overlaps the previous cursor by five minutes; recent Data Safe event IDs
   remove duplicates.
4. The function normalizes the audit event, applies privacy controls, and sends
   bounded batches to one OCI Logging custom log.
5. Connector Hub continuously transfers that log to a Log Analytics log group.
6. The custom `OCI Data Safe Database Audit` source maps JSON properties to
   real Log Analytics display fields.
7. Fifty-two generated saved searches power seven Management Dashboards.

## Why `timeCollected` is the cursor

`auditEventTime` is when the database event occurred. `timeCollected` is when
Data Safe received it. A collection-time cursor prevents delayed collection
from being skipped. Interactive Data Safe preflight checks still use bounded
`auditEventTime` filters to prove recent source activity.

## Delivery guarantees

The exporter is at-least-once:

- Object Storage ETag protection prevents concurrent invocations from silently
  overwriting each other's cursors.
- The overlap window protects the boundary between invocations.
- The cursor stores the most recent 5,000 Data Safe event IDs to suppress
  overlap duplicates.
- The cursor advances only after every Logging batch succeeds.
- If the per-run cap is reached, the cursor advances only to the last exported
  collection time.

Connector Hub is another at-least-once hop. Dashboard aggregations should use
the stable Data Safe Event ID for deduplication if an environment observes
Connector Hub replay.

## Supported dashboard navigation

OCI Management Dashboards currently documents individual custom dashboards and
global scope/time filters. This repository therefore deploys a supported suite
of seven consistently prefixed dashboards, each tagged with a stable logical tab
identifier. The generated bundle includes ordered navigation metadata for
future consumers.

The Management Dashboard API still exposes a legacy `SET` type, but the current
OCI documentation does not define its UI configuration contract. This project
does not emit undocumented SET payloads.

## What Terraform owns

- Cursor bucket
- OCI Logging group and custom log
- Function application and function
- Function invocation service log for runtime diagnosis
- Resource Scheduler schedule
- Connector Hub connector
- Optional dedicated Log Analytics log group
- Versioned Log Analytics fields/parser/source import
- Same-name Management Dashboard import
- Dynamic groups and policies when enabled

An existing Log Analytics log group can be supplied, or the stack can create a
dedicated group. The portable content package owns only the solution's fields,
parser, and source. The dashboard import owns only dashboards prefixed
`Data Safe Audit |`.

## OCI Logging wrapper contract

The Function writes a CloudEvents batch type of
`com.oraclecloud.logging.custom.datasafe.audit`. The Log Analytics source has
that exact immutable internal name and the reader-facing display name
`OCI Data Safe Database Audit`. Connector Hub uses the batch type to choose the
source automatically for a Logging source.

Connector Hub passes the value of OCI Logging's `logContent` object to the JSON
parser. Audit payload fields are therefore mapped from `$.data.<wire_field>`,
not `$.<wire_field>`. Content setup uses a two-phase source upsert because Log
Analytics derives a new source's immutable internal name from its initial
display name: it first creates the routing identifier and then updates only the
display name.
