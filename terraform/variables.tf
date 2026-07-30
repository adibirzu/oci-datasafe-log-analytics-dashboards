variable "oci_profile" {
  description = "OCI CLI profile used only by local Terraform. Resource Manager ignores this value."
  type        = string
  default     = "cap"
}

variable "tenancy_ocid" {
  description = "Tenancy OCID. Keep this in an uncommitted tfvars file."
  type        = string
  sensitive   = true
}

variable "compartment_ocid" {
  description = "Compartment for the solution resources."
  type        = string
  sensitive   = true
}

variable "data_safe_compartment_ocid" {
  description = "Compartment containing the Data Safe targets; it may differ from the solution compartment."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "OCI region for Data Safe, Functions, Logging, and Log Analytics."
  type        = string
}

variable "function_subnet_ocid" {
  description = "Existing regional subnet with OCI service access for the function."
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
}

variable "function_image" {
  description = "Immutable OCIR image URL including a digest or unique tag."
  type        = string
  default     = null
  nullable    = true
}

variable "log_analytics_log_group_ocid" {
  description = "Existing Oracle Log Analytics log group receiving Connector Hub data."
  type        = string
  sensitive   = true
}

variable "deployment_name" {
  type        = string
  default     = "datasafe-audit"
  description = "Tenant-neutral prefix for created resources."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.deployment_name))
    error_message = "deployment_name must be 3-25 lowercase letters, digits, or hyphens."
  }
}

variable "schedule_cron" {
  type        = string
  default     = "*/5 * * * *"
  description = "UTC UNIX cron expression for Resource Scheduler."
}

variable "include_sql_text" {
  type        = bool
  default     = false
  description = "Include SQL text in OCI Logging. False is the secure default."
}

variable "include_command_parameters" {
  type        = bool
  default     = false
  description = "Include SQL bind parameters. False is the secure default."
}

variable "hash_client_ip" {
  type        = bool
  default     = true
  description = "Pseudonymize client IPs while preserving grouping semantics."
}

variable "create_iam_resources" {
  type        = bool
  default     = true
  description = "Create tenancy-level dynamic groups and least-privilege policies."
}

variable "deploy_function" {
  type        = bool
  default     = true
  description = "Deploy the scheduled Function runtime. Set false for a profile-backed local E2E."
}

variable "freeform_tags" {
  type        = map(string)
  default     = {}
  description = "Additional non-confidential tags."
}
