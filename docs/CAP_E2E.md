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
- All seven unified audit trails were submitted for collection.
- Final unified-trail state: 4 `COLLECTING`, 3 `STOPPED_NEEDS_ATTN`.
- The first live Function export queried and exported 2,308 Data Safe events
  in 5 Logging batches, without truncation.
- A fresh release-gate invocation exported another 42 events.
- Connector Hub delivered schema-v2 records to Log Analytics.
- The three remaining target owners must run the target-specific Data Safe
  `datasafe_privileges.sql` workflow so the service account receives
  `AUDIT_COLLECTION`; grant `DV_MONITOR` too when Database Vault requires it.

This run **is** evidence of real Data Safe audit events reaching Log Analytics
through the deployed Function, Logging custom log, and Connector Hub.

## Downstream E2E

- Terraform plan: 6 additions, 0 changes, 0 destroys.
- Created: private versioned cursor bucket, custom Logging group/log, active
  Connector Hub route, generated pseudonymization salt, and scoped connector
  policy.
- Log Analytics content: 43 fields, one JSON parser, and one custom source.
- An earlier fabricated audit-shaped record was used only for downstream
  bring-up and was explicitly labeled synthetic.
- Final release evidence requires schema version `2.0` and a positive Function
  export count, excluding that synthetic record as source proof.
- Dashboard query parse checks: 52 passed, 0 failed.
- Dashboard views imported and present: 7 of 7.
- Terraform content/dashboard apply: 2 additions, 0 changes, 0 destroys.
- Post-apply local-state plan: no changes.
- Final downstream E2E status: ready.

## Function runtime gate

- ARM64 OCI Function image build: passed.
- Public OCIR release image publication through a secret-scoped workflow:
  passed.
- Temporary GitHub secrets, OCI auth tokens, and temporary push policies:
  deleted after each publication.
- ARM64 Function application/function deployment: passed.
- Function invocation service log deployment: passed.
- Synchronous Function invocation: passed.
- Active Resource Scheduler cadence: `0 */12 * * *`; next run populated.

## Closure criteria

The scheduled source-to-dashboard E2E is closed for four targets. Three target
database privilege gates remain independently open; they do not invalidate the
verified pipeline for the collecting targets.

## Publication gate

- The `main` branch was pushed to the dedicated private GitHub repository.
- The local verification passes 12 tests, Ruff, Terraform validation, the
  deterministic Resource Manager package test, 52 live query parses, and 7/7
  dashboard presence.
- Public release: `v2.0.2`.
- The release ZIP is anonymously downloadable and byte-identical to the
  locally verified deterministic package.
- GitHub Actions did not allocate a runner (`runner_id: 0`, no steps). Its
  annotation reports an account billing or spending-limit restriction. This is
  GitHub account infrastructure, not a repository test failure.
