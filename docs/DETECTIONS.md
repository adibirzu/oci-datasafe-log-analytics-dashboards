# Detection and alarm contract

Terraform creates eight Monitoring alarms. The Function idempotently reconciles
the eight exact-name Log Analytics saved searches and scheduled tasks on every
scheduled or synchronous invocation when `enable_detections=true`.
`scripts/deploy_detections.py` uses the same reconciliation contract for direct
operator runs. This is necessary because the Terraform provider scheduled-task
resource does not expose the `savedSearchDuration` action field. The searches
are bound to the customer-selected Log Analytics log group. The schedules emit
metrics in the customer-owned `datasafe_audit` namespace. No tenancy
identifier, database name, user name, or sample record is embedded in the
rules.

Resource Manager therefore has no post-apply workstation step: its first
Function invocation creates or updates the searches and schedules. The
Function policy receives saved-search and scheduled-task permissions only when
detections are enabled, and only in the selected solution compartment.
The Function uses bounded retry delays so reconciliation stays within its
configured invocation timeout.

| Rule | Default trigger | Severity |
|---|---:|---|
| Failed login spike | more than 10 per interval | Critical |
| Privilege or entitlement change | any event | Critical |
| Audit control change | any event | Critical |
| SQL Firewall violation | any event | Critical |
| Sensitive data access | any event | Warning |
| Data extraction spike | more than 1,000 per interval | Warning |
| Database error spike | more than 25 per interval | Warning |
| Administrative activity | more than 20 per interval | Warning |

The detection cadence is customer-selectable from five minutes to one hour.
Log Analytics offsets each window by 120 seconds for late-arriving records.
Thresholds are intentionally explicit Terraform data so a customer can review
and version-control changes.

Security Assessment and User Assessment drift are routed from native Data Safe
events to the configured Notifications topic. They are not synthesized from
audit events.

## Tuning

1. Keep rules enabled but alarms disabled during the observation period if
   notification noise is a concern.
2. Compare event volume by target, user, program, operation, and day/time.
3. Record the approved baseline and change thresholds through reviewed
   Terraform.
4. Add Notifications subscriptions in the customer tenancy; the solution
   creates a topic but never creates an external email or endpoint subscription.
5. Test each alarm with approved non-production database activity and retain
   evidence outside Git.

## Drilldown

Open **Data Safe Audit | Detection & Baseline**, set the Log Group Compartment,
Entity, and Time Range filters, then use a result row's fields to narrow the Log
Explorer search. The table queries preserve target, user, operation, object,
client program, action, and error dimensions needed for triage.
