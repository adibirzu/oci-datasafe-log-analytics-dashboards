variable "oci_profile" {
  description = "OCI CLI profile used only by local Terraform. Resource Manager ignores this value."
  type        = string
  default     = "cap"
}

variable "use_oci_profile" {
  description = "Use oci_profile for local CLI deployment. Keep false in Resource Manager."
  type        = bool
  default     = false
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
  default     = null
  nullable    = true
  sensitive   = true
}

variable "create_log_analytics_log_group" {
  type        = bool
  default     = false
  description = "Create a dedicated Log Analytics log group. If false, provide log_analytics_log_group_ocid."
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

variable "schedule_interval" {
  type        = string
  default     = "TWELVE_HOURS"
  description = "Function run interval: ONE_HOUR, SIX_HOURS, TWELVE_HOURS, ONE_DAY, or CUSTOM."
  validation {
    condition     = contains(["ONE_HOUR", "SIX_HOURS", "TWELVE_HOURS", "ONE_DAY", "CUSTOM"], var.schedule_interval)
    error_message = "schedule_interval must be ONE_HOUR, SIX_HOURS, TWELVE_HOURS, ONE_DAY, or CUSTOM."
  }
}

variable "custom_schedule_cron" {
  type        = string
  default     = ""
  description = "UTC UNIX cron expression used only when schedule_interval is CUSTOM."
}

variable "custom_initial_lookback_minutes" {
  type        = number
  default     = 750
  description = "First-run lookback used only with a custom schedule."
  validation {
    condition     = var.custom_initial_lookback_minutes >= 15 && var.custom_initial_lookback_minutes <= 10080
    error_message = "custom_initial_lookback_minutes must be between 15 minutes and seven days."
  }
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

variable "deploy_log_analytics_content" {
  type        = bool
  default     = true
  description = "Idempotently import the versioned Data Safe fields, parser, and source."
}

variable "deploy_dashboards" {
  type        = bool
  default     = true
  description = "Idempotently import all generated Management Dashboard views and saved searches."
}

variable "freeform_tags" {
  type        = map(string)
  default     = {}
  description = "Additional non-confidential tags."
}
