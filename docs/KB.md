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
