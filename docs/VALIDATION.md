# Production validation contract

Validation receipts are customer-environment artifacts and are excluded from
Git and release bundles. The public repository records only the validation
method; it never records a profile, tenancy, region, OCID, database, user,
address, raw event, live count, or error payload.

A production acceptance run must prove:

1. the selected OCI context authenticates and Log Analytics is onboarded;
2. at least one active Data Safe target has recent real audit activity;
3. the Function invocation exports a schema-v2 event;
4. OCI Logging contains the custom record and Connector Hub is active;
5. Log Analytics returns a positive count and non-zero target, user, and
   operation dimensions;
6. every canonical query parses;
7. exactly one copy of each of the eight dashboards exists;
8. all eight scheduled detections exist and are healthy;
9. all eight Monitoring alarms exist;
10. a follow-up Terraform plan shows no unexpected drift.

Run the gate with explicit customer context:

```bash
PYTHONPATH=src python scripts/e2e.py \
  --profile <OCI_PROFILE> \
  --compartment-id <SOLUTION_COMPARTMENT_OCID> \
  --deployment-name <DEPLOYMENT_NAME> \
  --invoke-function-id <FUNCTION_OCID> \
  --require-function-export \
  --deploy-dashboards
```

Write evidence only to an approved external evidence store. The default local
`evidence/live/` path is ignored by Git and must be removed when no longer
needed.

The release gate is fail-closed: an OCI API rejection while binding a
Management Saved Search to a Log Analytics scheduled task is a failed
deployment even when the query parses and dashboards contain data. Do not
publish a production release or enable its alarms until all eight tasks pass
item 8 above.
