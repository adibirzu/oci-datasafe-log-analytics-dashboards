# Data Safe visualization coverage

## Activity Auditing landing page

| Data Safe surface | OCI dashboard widget | View |
|---|---|---|
| Failed Login Activity | Failed Login Activity + Failed Login Trend | Activity Overview |
| Admin Activity | Admin Activity + Admin Activity Trend | Activity Overview |
| All Activity | All Activity + All Activity Trend | Activity Overview |
| Events Summary tab | Events Summary | Activity Overview |
| Targets Summary tab | Targets Summary | Activity Overview |

## Audit Insights

| Data Safe metric or chart | OCI dashboard widget |
|---|---|
| Targets | Targets |
| Database users | Database Users |
| Client hosts | Client Hosts |
| DDL commands | DDL Commands |
| User and entitlement changes | User & Entitlement Changes |
| DML commands | DML Commands |
| Login failures | Failed Login Activity |
| Events | All Activity |
| Targets by audit volume | Top Targets by Audit Volume |
| Audit policies by audit volume | Top Audit Policies by Volume |
| Schemas by audit volume | Top Schemas by Volume |
| Objects by audit volume | Top Objects by Volume |
| Database users by audit volume | Top Database Users by Volume |
| Client hosts by audit volume | Top Client Hosts by Volume |

## Added investigation views

The Identity & Access, Data & Schema, Client & Network, and Investigation views
are derived from the same Data Safe audit-event contract. They add time trends,
failure/error analysis, entitlement-change detail, sensitive activity, and
client-to-target pivots.

These views do not claim to reproduce Security Assessment, User Assessment,
Data Discovery, Data Masking, Alerts, or SQL Firewall dashboards. Those
features use different Data Safe APIs and are outside this audit-log pipeline.
