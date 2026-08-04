# OCI Data Safe to Log Analytics Knowledge Base

This knowledge base records only verified, reusable product behavior. It must
not contain OCIDs, namespaces, database names, IP addresses, user names, or live
error payloads.

## KB-001 — Blank dashboard widgets with a `localName` browser error

**Applies to:** Management Dashboard saved-search widgets.

**Symptom:** The dashboard exists, but every widget is blank or shows an error.
The browser console refers to reading `localName`.

**Cause:** Legacy widget metadata was used:
`visualizations/widgetTemplate.html` and `visualizations/widget`.

**Resolution:** Generate embedded saved searches with:

- `visualizations/chartWidgetTemplate.html`
- `jet-modules/dashboards/widgets/lxSavedSearchWidget`

**Verification:** Open the deployed dashboard, confirm the widgets render, and
confirm no new `localName` error appears in the browser console.

## KB-002 — Blank widgets or `fromOpaque`/`length` renderer errors

**Applies to:** Embedded Log Analytics saved searches.

**Symptom:** Queries parse successfully but dashboard widgets remain empty or
the browser console reports a scope conversion error.

**Cause:** `scopeFilters` is empty or incomplete. Parser validation does not
exercise the Management Dashboard scope renderer.

**Resolution:** Generate a complete compartment-scoped filter containing
`LogGroup`, `Entity`, `LogSet`, a `filters` list, and `isGlobal`. Runtime
deployment must substitute the customer compartment and never a repository
constant.

**Verification:** Confirm a real Log Analytics row, at least one expected
dimension, rendered widgets, and no new scope-renderer error.

## KB-003 — Scheduled task rejects an otherwise valid saved search

**Applies to:** Log Analytics scheduled searches and detection rules.

**Symptom:** The saved search is created, but scheduled-task creation rejects
its identifier.

**Cause:** The saved search has an invalid or incomplete runtime scope. Query
parse success and saved-search creation alone are insufficient evidence.

**Resolution:** Use the same complete compartment-scoped `scopeFilters`
contract as dashboard searches, then create or reconcile the scheduled task.

**Verification:** Require all expected scheduled tasks and alarms to exist and
be enabled. Re-running deployment must not create duplicates.

## KB-004 — Public screenshot evidence can leak tenant context

**Applies to:** README and operator documentation.

**Risk:** Console chrome, resource tables, drilldowns, or tooltips can expose
regions, OCIDs, target names, database identities, principals, or IP addresses.

**Resolution:** Publish only an intentionally cropped aggregate view. Exclude
console chrome, row-level tables, filters containing tenant values, and
drilldowns. Review the final pixels manually and run the repository leak gate.

**Verification:** A human review confirms that only dashboard labels, aggregate
counts, and charts remain.

## KB-005 — DDL, DML, schema, and object widgets all show no results

**Applies to:** Data & Schema and Audit Insights dashboards.

**Symptom:** Login or all-activity widgets contain data, while DDL/DML trends
and top schema/object widgets are empty.

**Cause:** The dashboard cannot manufacture audit events. If Data Safe is
collecting only login policies, the exported events have no DDL/DML operation
and no object owner, object name, or object type. A wider time range does not
resolve a policy-coverage gap.

**Resolution:**

- Enable and provision Data Safe's Database Schema Changes basic policy on the
  intended targets for DDL coverage.
- Define and enable appropriately scoped unified audit policies for DML writes
  (`INSERT`, `UPDATE`, `DELETE`, `MERGE`) and separately for data access
  (`SELECT`, `READ`, `EXECUTE`) where required. Avoid fleet-wide high-volume
  SELECT auditing without sizing, exclusions, and retention planning.
- Confirm the target audit trail is active, generate an authorized test action,
  wait for Data Safe collection and Function export, then validate the
  resulting Log Analytics row.

Data Safe's audit-event `Operation` is the generic action (`CREATE`, `ALTER`,
`DROP`); `Event Name` carries the specific action such as `CREATE TABLE`.
Queries must not require `Operation = 'CREATE TABLE'`.

**Verification:** Require positive, independently reported counts for DDL,
DML-write, and data-access categories as applicable, plus populated object
owner/name/type fields. An intentionally unused category must be marked
not-applicable instead of silently passing.

## KB-006 — E2E passes using data from an older Function deployment

**Applies to:** Local one-run deployment and production acceptance.

**Symptom:** Log Analytics rows, queries, dashboards, searches, and alarms pass
inventory checks even though the Function deployed in the current run was
never invoked.

**Cause:** A source query cannot distinguish newly exported data from
pre-existing rows. Running `scripts/e2e.py` without both
`--invoke-function-id` and `--require-function-export` validates available
data, not the current Function-to-Logging path.

**Resolution:** Resolve the Function ID from the applied Terraform state,
invoke that exact Function synchronously, and require a positive schema-v2
export before querying Log Analytics.

**Verification:** The invocation reports a positive export and the subsequent
Log Analytics query returns schema-v2 rows. Separately inspect OCI Logging,
Connector Hub delivery, scheduled-task health, alarm enabled state, and
Terraform drift; the automated E2E inventory does not prove those states.

## KB-007 — E2E cannot decode a successful Function export receipt

**Applies to:** Synchronous OCI Functions invocation in `scripts/e2e.py`.

**Symptom:** The E2E run fails immediately after a successful synchronous
Function invocation, before it can poll Log Analytics.

**Cause:** The OCI SDK returns the invocation body as a streaming HTTP response
whose bytes are in its `data` attribute. Converting the response object itself
to `bytes` does not read that payload.

**Resolution:** Decode the response through
`oci_datasafe_exporter.oci_response.response_bytes`, then validate the
privacy-safe JSON export receipt before accepting its `exported` count.

**Verification:** The focused tests cover raw, `content`, and streaming `data`
payload shapes. A live run must still invoke the exact applied Function and
observe a positive export before validating the downstream row.

## KB-008 — A current export receipt can match a historical Log Analytics row

**Applies to:** Function-to-Log-Analytics E2E acceptance.

**Symptom:** The Function reports a positive export and the source query returns
rows, but the query could be satisfied by a prior export.

**Cause:** Data Safe audit timestamps describe the audited database action, not
the Function invocation. A source-wide schema-version query has no fresh-run
correlation key.

**Resolution:** E2E supplies a newly generated opaque `export_run_id`. The
Function accepts only the expected fixed-width marker, attaches it to exported
records, and the E2E source and dimension queries require that same marker.

**Verification:** The marker is absent from public receipts and dashboards. A
live E2E run must return a positive count only for the newly generated marker.

## KB-009 — Content and dashboards exist but the E2E source has no rows

**Applies to:** Partial or manually assembled Log Analytics deployments.

**Symptom:** Query parsing and dashboard inventory succeed, but the canonical
source count is zero and no Function export can be validated.

**Cause:** Parser/source content and Management Dashboards are independent of
the Function, OCI Logging custom log, and active Connector Hub route. Their
presence alone does not create the ingestion path.

**Resolution:** Use read-only discovery to confirm an active connector with the
expected solution identity. If it is absent, obtain the reviewed Function
subnet, immutable image, and deployment inputs, review the Terraform plan, and
apply the full stack rather than treating the content-only state as E2E-ready.

**Verification:** Invoke the exact applied Function and require a positive count
for its fresh `export_run_id`; then verify the Connector Hub is active and the
full dashboard, task, and alarm inventory is healthy.

## KB-010 — Resource Manager finishes without Log Analytics detection schedules

**Applies to:** Terraform/Resource Manager deployments with detections enabled.

**Symptom:** Alarms exist after Terraform applies, but the expected saved
searches and scheduled tasks do not.

**Cause:** The Terraform provider scheduled-task resource lacks the
`savedSearchDuration` action property required by the supported detection
contract. A local CLI provisioner would also require a workstation profile and
is not portable to Resource Manager.

**Resolution:** Package the tenant-neutral rule catalog with the Function and
reconcile the exact-name searches and tasks under its resource principal on a
scheduled or synchronous Function invocation. Grant only compartment-scoped
data-plane access plus the tenancy-scoped saved-search and scheduled-task verbs
required by those OCI control-plane APIs when detections are enabled.

**Verification:** After the first Function invocation, require all expected
saved searches, scheduled tasks, and enabled alarms without duplicates. A real
Log Analytics row and rendered dashboards remain separate E2E requirements.

## KB-011 — Direct operator script fails before argument validation

**Applies to:** The discovery, E2E, Log Analytics content setup, and content
export scripts.

**Symptom:** A direct `python scripts/<name>.py --help` invocation fails with a
module-import error unless the caller manually configures `PYTHONPATH`.

**Cause:** The installable package uses a `src` layout, but direct scripts run
from the `scripts` directory rather than the project import root.

**Resolution:** Each direct entrypoint adds the project `src` directory before
loading package modules. This keeps profile, credentials, and target selection
explicit while removing a shell-session prerequisite.

**Verification:** Invoke each affected script with `--help` in an environment
with `PYTHONPATH` removed; it must return successfully.

## KB-012 — OCI SDK exception leaks service metadata to terminal output

**Applies to:** Read-only discovery and E2E CLI entrypoints.

**Symptom:** An invalid or unavailable target prints an OCI SDK traceback that
can contain request metadata or service-returned details.

**Cause:** The CLI allowed `ServiceError` to escape the entrypoint.

**Resolution:** Catch OCI service exceptions at the CLI boundary and emit only
a stable status/reason JSON result. Preserve diagnostic detail in approved,
access-controlled observability tooling rather than terminal evidence.

**Verification:** A focused test raises a synthetic service error and confirms
that the emitted result contains no supplied message text.

## KB-013 — OCI Functions rejects a digest-form image reference

**Applies to:** Terraform and Resource Manager Function deployment.

**Symptom:** Terraform creates supporting resources but Function creation fails
with an invalid-image validation error when `function_image` uses `@sha256`.

**Cause:** OCI Functions requires the OCIR image URL with a tag rather than a
digest-form reference.

**Resolution:** Push a uniquely versioned image tag and use that exact tag in
the Terraform or Resource Manager input. Do not reuse a release tag.

**Verification:** The Terraform precondition rejects digest-form input before
apply; Function creation succeeds with the pushed unique tag.

## KB-014 — Saved-search update returns not found after list and get succeed

**Applies to:** Function-based Log Analytics detection reconciliation.

**Symptom:** The resource principal can list and get an exact-name Management
Saved Search, but the update operation returns not found for the same resource.
Broadening `management-saved-search` or `loganalytics-scheduled-task` IAM does
not resolve it.

**Cause:** The Management Dashboard update endpoint does not accept the
Log Analytics saved-search instance even though the list and get endpoints
return it. This is an API operation behavior, not an authorization denial.

**Resolution:** Compare the solution-owned fields first and skip an unnecessary
update when they already match. For genuine drift, attempt update with the
current ETag; only an update-specific not-found response triggers an exact-ID,
ETag-protected delete and recreate. Other status categories remain fail-closed.

**Verification:** A resource-principal invocation returns a successful redacted
receipt with eight detections, and repeated invocations retain the exact-name
inventory without duplicates.

## KB-015 — Fresh Function export is not immediately queryable in Log Analytics

**Applies to:** Function-to-OCI-Logging-to-Connector-Hub-to-Log-Analytics E2E.

**Symptom:** The synchronous Function receipt reports a positive export, while
the fresh opaque E2E marker has no Log Analytics rows during a short poll.
Unmarked source rows and earlier opaque markers remain queryable.

**Cause:** The Function completion confirms OCI Logging ingestion, not
completion of the asynchronous Connector Hub delivery into Log Analytics.

**Resolution:** Keep the marker requirement and poll the marker-specific query
for a bounded ten minutes by default. Do not substitute an unmarked historical
row or the Function receipt for the downstream row proof.

**Verification:** The same invocation's positive export count equals the
marker-filtered Log Analytics row count, with populated target, user, and
operation dimensions.

## Required component evidence

Every production change must either add a new KB entry or state that no new
failure mode was discovered.

| Component | Required evidence |
|---|---|
| Queries | Local schema tests, live parse, and at least one real row or an explicitly documented data prerequisite |
| Dashboards | Exact inventory, no duplicates, rendered widgets, expected dimensions, and a clean browser console |
| Sources/parsers/fields | Reconciliation is idempotent and uses only runtime customer identifiers |
| Function/ingestion | A successful invocation plus a real Log Analytics row carrying the canonical source and fields |
| Detections/alarms | Saved search, scheduled task, and enabled alarm counts match the generated inventory |
| Terraform/Resource Manager | Plan/package validation, IAM coverage, deploy verification, rollback, and destroy verification |
| LLM or compute extensions | Add a component-specific row and KB entry before introducing either surface; neither is part of the current runtime |

The shared OCI Log Analytics skill also documents field typing, subtree scope,
time-window handling, optimistic concurrency, and live-validation constraints.
