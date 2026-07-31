# Repository agent rules

- Never commit OCIDs, API keys, auth tokens, public IPs, database names,
  tenancy namespaces, or live error payloads.
- `dashboards/queries/*.json` is the canonical query surface.
- `dashboards/generated_bundle.json` must be regenerated, not hand-edited.
- Keep the custom source name `OCI Data Safe Database Audit` aligned across the
  Logging batch type, parser/source setup, and every query.
- Timestats queries must use line visualizations with explicit time/value
  fields. Aggregated rollups use tile, bar, hbar, or summary table.
- Live OCI writes require explicit profile and compartment arguments.
- A parse success or HTTP 200 is not E2E proof; require a real Log Analytics
  row and deployed dashboard presence.
- Preserve privacy defaults unless the user explicitly approves a different
  data-processing posture.
- Use `skills/oci-log-analytics-dashboard-enhancer/SKILL.md` for dashboard,
  visualization, drilldown, or detection-scheduling changes.
- Search `docs/KB.md` before debugging. After verification, add a KB entry for
  every newly confirmed component failure mode.
- Dashboard acceptance requires rendered data and a clean browser console;
  query parsing and resource presence alone are insufficient.
