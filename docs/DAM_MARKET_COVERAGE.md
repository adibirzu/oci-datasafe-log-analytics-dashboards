# Database activity monitoring coverage

This solution uses public product documentation to identify common database
activity monitoring (DAM) operator views. It does not copy proprietary vendor
dashboards, labels, sample records, or customer data.

## Reference capabilities

| Operator need | Reference capability | Implementation |
|---|---|---|
| Executive database-risk view | IBM Guardium documents executive risk/compliance dashboards and activity, error, and violation trends. | Activity Overview and Detection & Baseline tabs |
| New identities and clients | Guardium Insights documents “new this week” views for database users, OS users, source programs, and client IPs. | Identity & Access and Client & Network tabs |
| Account misuse and access hygiene | Guardium documents shared/risky accounts and account-related activity. Oracle User Assessment identifies highly privileged and risky accounts. | Failed login, entitlement change, admin activity, user activity, and native User Assessment drift |
| Security configuration drift | Data Safe Security Assessment compares database configuration with Oracle and industry practices; Data Safe assessments support baselines and drift events. | Native Security Assessment baseline event routed to Notifications |
| Sensitive-data access | Data Safe Data Discovery classifies sensitive columns; Activity Auditing supplies matching activity. | Sensitive Data Access detection and Data & Schema drilldown |
| SQL injection or unauthorized SQL | IBM describes SQL injection and data-leakage threat views. Data Safe SQL Firewall reports SQL violations. | SQL Firewall detection and predefined report |
| Audit coverage and retention | Data Safe audit profiles define online/offline retention and audit trails expose collection state. | Operations checks and discovery report; trail state remains authoritative in Data Safe |
| Compliance and investigation | Guardium documents compliance workspaces and reports; Data Safe provides predefined audit reports. | Predefined Reports and Investigation tabs |

## Design choices

- Data Safe remains the source of truth for target registration, assessment
  findings, assessment baselines, sensitive-data models, audit profiles, audit
  trails, and SQL Firewall policy.
- Log Analytics holds normalized audit activity and provides fleet-wide
  investigation, customer-controlled retention, saved searches, scheduled
  detections, and dashboard drilldowns.
- Monitoring alarms use metrics emitted by Log Analytics detection rules.
  Security Assessment and User Assessment drift use Data Safe's native events,
  because an audit-volume approximation is not equivalent to assessment drift.
- Thresholds are deployable defaults, not a customer's approved baseline.
  Operators must tune them after observing normal workload and document the
  approved value.

## Public references

- [Oracle Data Safe overview](https://docs.oracle.com/en-us/iaas/data-safe/doc/oracle-data-safe-overview.html)
- [Oracle Data Safe User Assessment](https://docs.oracle.com/en-us/iaas/data-safe/doc/user-assessment-overview.html)
- [Oracle Data Safe audit profiles](https://docs.oracle.com/en-us/iaas/data-safe/doc/audit-profiles.html)
- [Oracle Log Analytics detection rules](https://docs.oracle.com/en-us/iaas/log-analytics/doc/manage-detection-rules.html)
- [Oracle Log Analytics scheduled searches](https://docs.oracle.com/en-us/iaas/log-analytics/doc/create-schedule-run-saved-search.html)
- [IBM Guardium Insights dashboards](https://www.ibm.com/docs/en/guardium-insights/3.x?topic=data-dashboards)
- [IBM Guardium Data Protection dashboard](https://www.ibm.com/docs/en/gdp/11.5.0?topic=audit-data-protection-dashboard)
