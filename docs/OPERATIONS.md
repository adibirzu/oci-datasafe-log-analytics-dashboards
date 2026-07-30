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

## Synthetic downstream E2E

When the Data Safe source is unavailable, an operator may validate only the
downstream Logging-to-dashboard path with `scripts/send_synthetic_event.py`.
The command requires `--acknowledge-synthetic`, uses visibly synthetic values,
and must never be reported as proof that Data Safe collection is working.

## Upgrade

1. Run local `make verify`.
2. Build and scan a uniquely tagged function image.
3. Review Terraform plan.
4. Apply and invoke once manually.
5. Run `scripts/e2e.py` and preserve the redacted receipt outside Git.
6. Confirm the scheduled invocation before closing the change.
