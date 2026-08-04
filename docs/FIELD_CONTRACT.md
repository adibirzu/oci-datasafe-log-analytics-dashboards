# Log Analytics field contract

The exporter maps every functional property currently returned by Data Safe's
`AuditEventSummary` into the `OCI Data Safe Database Audit` JSON contract,
except free-form and defined tags. Tags are deliberately excluded because they
are not audit-event facts and can contain tenancy-specific or confidential
metadata.

## Identity and target

`id`, `compartment_id`, `target_id`, `target_name`, `target_class`,
`database_type`, `database_unique_name`, `peer_target_database_key`,
`db_user_name`, `external_user_id`, and `target_user`.

## Event and collection

`audit_event_time`, `time_collected`, `operation`, `operation_status`,
`event_name`, `action_taken`, `audit_type`, `audit_trail_id`,
`audit_location`, and `trail_source`.

## Client and operating system

`client_ip`, `client_hostname`, `client_program`, `client_id`,
`os_user_name`, `os_terminal`, and `application_contexts`.

## Object, policy, SQL, and errors

`object_owner`, `object_name`, `object_type`, `audit_policies`,
`fga_policy_name`, `error_code`, `error_message`, `command_text`,
`command_param`, and `extended_event_attributes`.

`command_text` and `command_param` are omitted unless explicitly enabled.
`client_ip` is pseudonymized by default.

## Data Safe filter-only classifications

`admin_user`, `common_user`, `sensitive_activity`, and `ds_activity` are not
returned on `AuditEventSummary`. The Function queries each Data Safe
classifier over the exact bounded collection-time window and joins matching
event IDs into the exported records as numeric `0`/`1` fields.

Every record also includes `schema_version=2.0`. An E2E-triggered export also
includes an opaque, per-invocation `export_run_id`; it is used only to prove
that the newly invoked Function reached Log Analytics and is not shown in
dashboards or public evidence. The portable content bundle contains 44
reader-facing Log Analytics fields (including Schema Version and Export Run ID),
the JSON parser, and the canonical source. Built-in Log Analytics fields are
reused rather than duplicated.

## Semantic and privacy contract

Fields follow four rules:

1. Preserve the literal OCI Data Safe SDK property as the stable wire key.
2. Use a readable Log Analytics display name, without tenant-specific aliases.
3. Keep identifiers as strings; never coerce OCIDs, database identifiers,
   usernames, error codes, or classifier values into misleading types.
4. Minimize sensitive content: SQL text and parameters are opt-in, client IP is
   pseudonymized by default, and tags are excluded.

| Data class | Examples | Default handling |
|---|---|---|
| OCI identifiers | compartment, target, trail IDs | Runtime customer values only; never committed or emitted in evidence |
| Database identity | database user, target user, OS user | Exported for audit purpose; access-controlled in Logging and Log Analytics |
| Network identity | client IP, host, terminal | IP pseudonymized; other values retained for investigation |
| Database object | owner, name, type, policy | Retained for audit and drilldown |
| Potential content | SQL text, bind parameters, contexts | SQL and binds disabled; structured contexts serialized deterministically |
| Detection classifiers | admin, common, sensitive, Data Safe activity | Numeric `0` or `1`, suitable for filtering and metrics |
| Time | audit event and collection time | RFC 3339 UTC string; OCI Logging entry time uses audit time when available |

The display-field vocabulary maps directly to Data Safe rather than inventing
generic placeholders. Integrations can map it to OCSF Database Activity or an
enterprise canonical model downstream without changing the source parser.
