---
name: oci-log-analytics-dashboard-enhancer
description: Use when creating, repairing, validating, or documenting OCI Log Analytics saved searches, Management Dashboards, drilldowns, detections, alarms, and Data Safe audit visualizations in this repository.
---

# OCI Log Analytics Dashboard Enhancer

Use this skill with the shared `oci-log-analytics` and `oci-data-safe` skills.
Read `docs/KB.md` before changing queries, dashboards, or detection scheduling.

## Safety contract

- Never hard-code or commit OCIDs, namespaces, database names, target names,
  IPs, principals, profiles, or live payloads.
- All customer identifiers enter through explicit variables or resolved
  Terraform outputs.
- Keep queries time-agnostic; the dashboard or scheduled task supplies time.
- Reconcile by stable generated identity. A second deployment must update or
  reuse content, not duplicate it.
- Public screenshots may contain aggregate charts only.

## Current dashboard contract

Embedded Log Analytics saved searches must use:

- `visualizations/chartWidgetTemplate.html`
- `jet-modules/dashboards/widgets/lxSavedSearchWidget`
- a complete runtime `scopeFilters` object with `LogGroup`, `Entity`, `LogSet`,
  `filters`, and `isGlobal`

Never accept an empty `scopeFilters`. Query parse success does not validate the
Management Dashboard renderer.

## Visualization rules

- `tile`: one aggregate value with an explicit data field.
- `line`: `timestats` with explicit time and value fields.
- `bar`/`hbar`: bounded categorical `stats` output.
- `summary_table`: grouped rollups and investigation pivots.
- Preserve target, database, operation, user, severity, and time fields needed
  for dashboard filters and drilldowns without exposing their live values.

## Required verification

Run the repository verification gate, then perform the authorized live gate:

1. Rebuild the canonical bundle; never hand-edit it.
2. Parse every generated query.
3. Confirm a real Log Analytics row and expected dimensions.
4. Reconcile the exact dashboard inventory and prove zero duplicates.
5. Open representative dashboards and prove no new `localName`, `fromOpaque`,
   scope, or refresh errors in the browser console.
6. Reconcile detection saved searches, scheduled tasks, and enabled alarms.
7. Re-run deployment to prove idempotency.
8. Run the tenant leak gate and manually inspect every publishable screenshot.
9. Add or update `docs/KB.md` for each newly verified failure mode.

Local tests, synthetic fixtures, HTTP success, and parser success are not live
end-to-end evidence.
