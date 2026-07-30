resource "random_password" "client_ip_salt" {
  length  = 32
  special = false
}

locals {
  tags = merge(
    {
      "solution"   = "oci-datasafe-log-analytics"
      "managed-by" = "terraform"
    },
    var.freeform_tags
  )
}

resource "oci_objectstorage_bucket" "cursor" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.current.namespace
  name           = "${var.deployment_name}-cursor"
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
  versioning     = "Enabled"
  freeform_tags  = local.tags
}

data "oci_objectstorage_namespace" "current" {
  compartment_id = var.tenancy_ocid
}

resource "oci_logging_log_group" "audit" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.deployment_name}-logging"
  description    = "Data Safe database audit events before Log Analytics routing."
  freeform_tags  = local.tags
}

resource "oci_logging_log" "audit" {
  display_name  = "${var.deployment_name}-events"
  log_group_id  = oci_logging_log_group.audit.id
  log_type      = "CUSTOM"
  is_enabled    = true
  freeform_tags = local.tags
}

resource "oci_functions_application" "audit" {
  count          = var.deploy_function ? 1 : 0
  compartment_id = var.compartment_ocid
  display_name   = "${var.deployment_name}-exporter"
  subnet_ids     = [var.function_subnet_ocid]
  shape          = "GENERIC_ARM"
  freeform_tags  = local.tags
  lifecycle {
    precondition {
      condition     = var.function_subnet_ocid != null && can(regex("^ocid1\\.subnet\\.", var.function_subnet_ocid))
      error_message = "function_subnet_ocid is required when deploy_function is true."
    }
  }
}

resource "oci_functions_function" "audit" {
  count              = var.deploy_function ? 1 : 0
  application_id     = oci_functions_application.audit[0].id
  display_name       = "${var.deployment_name}-export"
  image              = var.function_image
  memory_in_mbs      = 1024
  timeout_in_seconds = 300
  freeform_tags      = local.tags
  config = {
    DATA_SAFE_COMPARTMENT_ID   = var.data_safe_compartment_ocid
    LOGGING_LOG_ID             = oci_logging_log.audit.id
    CURSOR_BUCKET_NAME         = oci_objectstorage_bucket.cursor.name
    CURSOR_OBJECT_NAME         = "${var.deployment_name}/cursor.json"
    INITIAL_LOOKBACK_MINUTES   = "60"
    CURSOR_OVERLAP_MINUTES     = "5"
    SAFETY_LAG_SECONDS         = "120"
    MAX_EVENTS_PER_RUN         = "50000"
    INCLUDE_SUBCOMPARTMENTS    = "true"
    INCLUDE_SQL_TEXT           = tostring(var.include_sql_text)
    INCLUDE_COMMAND_PARAMETERS = tostring(var.include_command_parameters)
    HASH_CLIENT_IP             = tostring(var.hash_client_ip)
    CLIENT_IP_HASH_SALT        = random_password.client_ip_salt.result
  }
  lifecycle {
    precondition {
      condition     = var.function_image != null && length(var.function_image) > 10
      error_message = "function_image is required when deploy_function is true."
    }
  }
}

resource "oci_resource_scheduler_schedule" "audit" {
  count              = var.deploy_function ? 1 : 0
  action             = "START_RESOURCE"
  compartment_id     = var.compartment_ocid
  recurrence_details = var.schedule_cron
  recurrence_type    = "CRON"
  display_name       = "${var.deployment_name}-schedule"
  description        = "Invokes the Data Safe audit export function."
  state              = "ACTIVE"
  freeform_tags      = local.tags

  resources {
    id = oci_functions_function.audit[0].id
  }
}

resource "oci_sch_service_connector" "audit" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.deployment_name}-logging-to-log-analytics"
  description    = "Routes Data Safe database audit events from OCI Logging to Oracle Log Analytics."
  state          = "ACTIVE"
  freeform_tags  = local.tags

  source {
    kind = "logging"
    log_sources {
      compartment_id = var.compartment_ocid
      log_group_id   = oci_logging_log_group.audit.id
      log_id         = oci_logging_log.audit.id
    }
  }

  target {
    kind         = "loggingAnalytics"
    log_group_id = var.log_analytics_log_group_ocid
  }
}
