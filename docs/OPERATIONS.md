# Operations runbook

## Healthy state

- Data Safe target databases are `ACTIVE`.
- Audit trails are `COLLECTING` or `IDLE`.
- Resource Scheduler is active and reports successful recent runs.
- Function errors are zero and the cursor object's `updatedAt` advances.
- Connector Hub is `ACTIVE` and its run log reports records written.
- The source query returns rows within the expected lag:

```text
'Log Source' = 'OCI Data Safe Database Audit' | stats count as Events
```

- All dashboard queries parse and each expected dashboard exists.

## Schedule

`schedule_interval` controls Resource Scheduler:

| Selection | UTC cron | First-run lookback |
|---|---:|---:|
| `ONE_HOUR` | `0 * * * *` | 75 minutes |
| `SIX_HOURS` | `0 */6 * * *` | 390 minutes |
| `TWELVE_HOURS` (default) | `0 */12 * * *` | 750 minutes |
| `ONE_DAY` | `0 0 * * *` | 1,470 minutes |
| `CUSTOM` | `custom_schedule_cron` | `custom_initial_lookback_minutes` |

Every later run resumes from the Object Storage cursor and overlaps by five
minutes, so changing cadence does not reset or skip the cursor.

## Data Safe database privileges

An active registered target is not sufficient: each audit trail must be
started and the Data Safe service account needs `AUDIT_COLLECTION`. Download
the target-specific `datasafe_privileges.sql` script from Data Safe, run it as
an authorized database administrator, and enable `DV_MONITOR` when Database
Vault collection is required. Then start the trail and verify it reaches
`COLLECTING` or `IDLE`. The exporter cannot grant database privileges through
OCI IAM.

When targets span unrelated top-level compartments, set
`data_safe_compartment_ocid` to the tenancy OCID. The generated IAM policy then
uses `in tenancy`; otherwise it is restricted to the selected compartment ID.

## No events

1. Check the Data Safe target and audit-trail states.
2. Run `scripts/preflight.py --data-safe-compartment-id <OCID>
   --solution-compartment-id <OCID>`; a false recent-event check is a source
   condition, not a Log Analytics failure.
3. Check the function invocation result and the cursor update time.
4. Search OCI Logging for the custom log before investigating Connector Hub.
5. Check the connector lifecycle/run log and IAM policy.
6. Query the canonical source over a wider window and include
   subcompartments. An empty result is inconclusive until source, scope, and
   window are verified.
7. If the trail is `STOPPED_NEEDS_ATTN`, inspect its Data Safe error. Missing
   `AUDIT_COLLECTION` is a database-side prerequisite, not a Function,
   Connector Hub, parser, or dashboard defect.

### Every dashboard says `No data to display`

1. Query
   `'Log Source' = 'OCI Data Safe Database Audit' | stats count as Events`.
   `Events` must be greater than zero. An aggregate row containing `Events: 0`
   is not ingestion proof.
2. Query schema-v2 records and require positive distinct counts for
   `Data Safe Target Name`, `Database User`, and `Operation`. A positive event
   count with zero dimensions means the source matched but the JSON parser did
   not map OCI Logging's `logContent.data` wrapper.
3. Fetch the dashboard and verify every embedded saved search has complete
   `LogGroup`, `Entity`, `LogSet`, `filters`, and `isGlobal` scope entries.
   Deployment substitutes the selected customer compartment before dashboard
   parameters apply user overrides. An empty scope object causes the current
   Log Analytics widget to fail before query execution.
4. Verify exactly one dashboard exists for each of the eight suite names.
   `scripts/deploy_dashboards.py --cleanup-duplicates` retains the newest copy
   after a successful import.
5. Confirm the Log Group Compartment filter selects the solution compartment
   and the time range covers the latest export.

The live E2E gate enforces a positive source count, populated customer
dimensions, all query parses, and exactly one deployed dashboard per suite view.

## Cursor recovery

The cursor bucket has versioning enabled. Restore an earlier cursor object
version only after stopping the schedule. Replaying an old cursor is safe but
may produce duplicates. Never move the cursor forward manually without
record-level reconciliation.

## Backfill

Increase `INITIAL_LOOKBACK_MINUTES` only for an empty cursor. For an existing
deployment, create a separate cursor object name for a controlled backfill.
Connector Hub's Logging-source retention is 24 hours; historical data must be
re-exported through the function so it becomes new OCI Logging content.

## Upgrade

1. Run local `make verify`.
2. Build and scan a uniquely tagged function image.
3. Review Terraform plan.
4. Apply and invoke once manually.
5. Run `scripts/e2e.py` and preserve the redacted receipt outside Git.
   Use `--invoke-function-id <FUNCTION_OCID> --require-function-export` for
   release evidence; this requires a positive export count and a schema-v2 row
   in Log Analytics.
6. Confirm the scheduled invocation before closing the change.

## Idempotent repair

- `scripts/setup_log_analytics_content.py` reuses display/internal field names,
  updates the parser with its ETag, and upserts the existing source.
- Terraform imports `terraform/content/oci-datasafe-log-analytics-content.zip`
  with overwrite enabled.
- Dashboard import sets same-name replacement, so the eight suite dashboards
  and their saved searches are updated rather than duplicated.
- The Connector Hub connector is a normal Terraform resource; repeated plans
  preserve it unless the reviewed configuration changes.
