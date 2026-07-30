# Security model

## Data minimization

The exporter excludes `commandText` and `commandParam` by default because they
can contain personal data, application secrets, or business records. Client IP
addresses are pseudonymized with SHA-256 and a random per-deployment salt. The
salt is sensitive Terraform state and is passed to the function configuration;
it is never committed.

Set `include_sql_text` or `include_command_parameters` only after data-owner,
privacy, and retention review. Enabling these settings is a materially
different data-processing posture.

## IAM

The function can:

- read Data Safe audit events;
- write the one OCI Logging compartment;
- manage objects only in the named cursor bucket;
- read the Object Storage namespace.

Resource Scheduler can invoke functions in the solution compartment. Connector
Hub can read Logging content in the solution compartment and write only the
specified Log Analytics log group.

Review tenancy-level policy creation before apply. Set
`create_iam_resources=false` only when equivalent owner-managed policies
already exist.

## Secrets and state

- Keep Terraform state in an encrypted, access-controlled backend.
- Do not commit `terraform.tfvars`, state, plans, E2E evidence, or OCI CLI
  configuration.
- Use immutable OCIR image tags and repository scanning.
- Restrict access to OCI Logging and Log Analytics because normalized audit
  records still contain database identities and activity.

## Safe testing

E2E testing generates no database exploit activity. It exports existing Data
Safe audit records and validates the resulting ingestion and dashboards. A
separate non-production database transaction may be used when a deterministic
marker event is required.
