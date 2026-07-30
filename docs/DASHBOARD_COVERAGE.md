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

## Predefined Activity Auditing reports

The `Predefined Reports` dashboard recreates every predefined report currently
listed by Data Safe Activity Auditing:

| Data Safe report | Log Analytics saved search |
|---|---|
| All Activity | All Activity Report |
| Admin Activity | Admin Activity Report |
| User/Entitlement Changes | User and Entitlement Changes Report |
| Audit Policy Changes | Audit Policy Changes Report |
| Login Activity | Login Activity Report |
| Data Access | Data Access Report |
| Data Modification | Data Modification Report |
| Database Schema Changes | Database Schema Changes Report |
| Data Safe Activity | Data Safe Activity Report |
| Database Vault Activity | Database Vault Activity Report |
| Common User Activity | Common User Activity Report |
| Database Error | Database Error Report |
| Data Extraction Activity | Data Extraction Activity Report |
| Sensitive Data Activity | Sensitive Data Activity Report |
| SQL Firewall audited violations | SQL Firewall Audited Violations Report |

Data Safe exposes administrator, common-user, sensitive-activity, and Data Safe
activity classifications only as audit-event filters. The exporter performs
four bounded classifier queries per run and joins those classifications to the
main audit-event set by stable Data Safe event ID.

## Added investigation views

The Identity & Access, Data & Schema, Client & Network, and Investigation views
are derived from the same Data Safe audit-event contract. They add time trends,
failure/error analysis, entitlement-change detail, sensitive activity, and
client-to-target pivots.

These views do not export raw Security Assessment, User Assessment, Data
Discovery, Data Masking, or Alert payloads. Those features use different Data
Safe API contracts and can contain findings or sensitive-data metadata that do
not belong in a database-audit log pipeline. This suite covers the Activity
Auditing landing page, Audit Insights, every predefined audit report (including
audited SQL Firewall violations), and additional audit-event analytics.
