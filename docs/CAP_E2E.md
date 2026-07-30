# CAP E2E validation

Validation date: 2026-07-30
Region: `eu-frankfurt-1`

This receipt deliberately separates real source readiness from a synthetic
downstream transport test. It contains no tenancy identifiers, target names,
database names, addresses, or live error payloads.

## Real Data Safe source gate

- Profile authentication: passed.
- Active Data Safe targets discovered: 7.
- Audit trails discovered: 13.
- Initial audit-trail state: all `INACTIVE` / `NOT_STARTED`.
- One unified audit trail was started with a one-hour collection window.
- Data Safe accepted the work request, but the database-side operation failed.
- Required owner action: run the Data Safe `datasafe_privileges.sql` grant
  workflow so the service account receives `AUDIT_COLLECTION`; grant
  `DV_MONITOR` too when Database Vault requires it.
- Profile-backed exporter result: 0 queried, 0 exported, 0 batches.

Therefore, this run is **not** evidence of a live Data Safe audit event reaching
Log Analytics.

## Synthetic downstream E2E

- Terraform plan: 6 additions, 0 changes, 0 destroys.
- Created: private versioned cursor bucket, custom Logging group/log, active
  Connector Hub route, generated pseudonymization salt, and scoped connector
  policy.
- Log Analytics content: 33 fields, one JSON parser, and one custom source.
- Fabricated audit-shaped records written: 1, explicitly labeled synthetic.
- Real Log Analytics row observed after Connector Hub delivery: yes.
- Dashboard query parse checks: 37 passed, 0 failed.
- Dashboard views imported and present: 6 of 6.
- Final downstream E2E status: ready.

## Function runtime gate

- ARM64 OCI Function image build: passed.
- Private OCIR repository creation: passed.
- Image push: blocked by OCIR authentication (`Unauthorized`).
- Temporary authentication tokens used during diagnostics were deleted
  immediately, and Docker was logged out.
- Scheduled Function deployment was intentionally skipped; the same exporter
  was exercised locally with the `cap` API-key profile.

## Closure criteria

The full scheduled source-to-dashboard E2E closes only when:

1. the database owner applies the Data Safe collection privilege script;
2. at least one audit trail is collecting and a real event is visible;
3. an operator supplies working OCIR push credentials;
4. the Function and schedule are deployed and invoked;
5. `scripts/e2e.py` passes using that Function invocation, with no synthetic
   record used as source proof.

## Publication gate

- The `main` branch was pushed to the dedicated private GitHub repository.
- The local pre-push verification passed all 9 tests.
- GitHub Actions did not allocate a runner (`runner_id: 0`, no steps). Its
  annotation reports an account billing or spending-limit restriction. This is
  GitHub account infrastructure, not a repository test failure.
