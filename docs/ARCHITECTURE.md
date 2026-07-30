# Architecture and delivery boundaries

## Data path

1. Data Safe collects unified database audit records into its regional
   repository.
2. Resource Scheduler invokes the exporter function on a five-minute cron.
3. The function reads a bounded `timeCollected` SCIM window. The window
   overlaps the previous cursor by five minutes; recent Data Safe event IDs
   remove duplicates.
4. The function normalizes the audit event, applies privacy controls, and sends
   bounded batches to one OCI Logging custom log.
5. Connector Hub continuously transfers that log to a Log Analytics log group.
6. The custom `OCI Data Safe Database Audit` source maps JSON properties to
   real Log Analytics display fields.
7. Generated saved searches power six Management Dashboards.

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
of six consistently prefixed dashboards, each tagged with a stable logical tab
identifier. The generated bundle includes ordered navigation metadata for
future consumers.

The Management Dashboard API still exposes a legacy `SET` type, but the current
OCI documentation does not define its UI configuration contract. This project
does not emit undocumented SET payloads.

## What Terraform owns

- Cursor bucket
- OCI Logging group and custom log
- Function application and function
- Resource Scheduler schedule
- Connector Hub connector
- Dynamic groups and policies when enabled

The Log Analytics log group is deliberately supplied as an existing resource.
The content setup script owns only the solution's fields, parser, and source.
The dashboard deployer owns only dashboards prefixed `Data Safe Audit |`.
