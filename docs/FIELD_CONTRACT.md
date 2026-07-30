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

Every record also includes `schema_version=2.0`. The portable content bundle
contains 43 reader-facing Log Analytics fields (including Schema Version),
the JSON parser, and the canonical source. Built-in Log Analytics fields are
reused rather than duplicated.
