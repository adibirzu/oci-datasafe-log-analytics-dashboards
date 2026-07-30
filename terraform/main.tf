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
  schedule_crons = {
    ONE_HOUR     = "0 * * * *"
    SIX_HOURS    = "0 */6 * * *"
    TWELVE_HOURS = "0 */12 * * *"
    ONE_DAY      = "0 0 * * *"
  }
  effective_schedule_cron = var.schedule_interval == "CUSTOM" ? var.custom_schedule_cron : local.schedule_crons[var.schedule_interval]
  initial_lookback_minutes = {
    ONE_HOUR     = 75
    SIX_HOURS    = 390
    TWELVE_HOURS = 750
    ONE_DAY      = 1470
    CUSTOM       = var.custom_initial_lookback_minutes
  }
  dashboard_bundle_file      = fileexists("${path.module}/dashboard_bundle.json") ? "${path.module}/dashboard_bundle.json" : "${path.module}/../dashboards/generated_bundle.json"
  log_analytics_namespace    = data.oci_log_analytics_namespaces.current.namespace_collection[0].items[0].namespace
  log_analytics_log_group_id = var.create_log_analytics_log_group ? oci_log_analytics_log_analytics_log_group.audit[0].id : var.log_analytics_log_group_ocid
}

data "oci_log_analytics_namespaces" "current" {
  compartment_id = var.tenancy_ocid
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

resource "oci_log_analytics_log_analytics_log_group" "audit" {
  count          = var.create_log_analytics_log_group ? 1 : 0
  compartment_id = var.compartment_ocid
  namespace      = local.log_analytics_namespace
  display_name   = "${var.deployment_name}-analytics"
  description    = "Log Analytics group for OCI Data Safe database audit events."
  freeform_tags  = local.tags
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
    INITIAL_LOOKBACK_MINUTES   = tostring(local.initial_lookback_minutes[var.schedule_interval])
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
  recurrence_details = local.effective_schedule_cron
  recurrence_type    = "CRON"
  display_name       = "${var.deployment_name}-schedule"
  description        = "Invokes the Data Safe audit export function."
  state              = "ACTIVE"
  freeform_tags      = local.tags

  lifecycle {
    precondition {
      condition     = var.schedule_interval != "CUSTOM" || length(trimspace(var.custom_schedule_cron)) > 0
      error_message = "custom_schedule_cron is required when schedule_interval is CUSTOM."
    }
  }

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
    log_group_id = local.log_analytics_log_group_id
  }

  lifecycle {
    precondition {
      condition     = local.log_analytics_log_group_id != null && can(regex("^ocid1\\.loganalyticsloggroup\\.", local.log_analytics_log_group_id))
      error_message = "Set create_log_analytics_log_group=true or provide log_analytics_log_group_ocid."
    }
  }
}

resource "oci_log_analytics_log_analytics_import_custom_content" "audit" {
  count                      = var.deploy_log_analytics_content ? 1 : 0
  namespace                  = local.log_analytics_namespace
  import_custom_content_file = "${path.module}/content/oci-datasafe-log-analytics-content.zip"
  is_overwrite               = true
}

resource "oci_management_dashboard_management_dashboards_import" "audit" {
  count                                  = var.deploy_dashboards ? 1 : 0
  import_details_file                    = local.dashboard_bundle_file
  override_dashboard_compartment_ocid    = var.compartment_ocid
  override_saved_search_compartment_ocid = var.compartment_ocid
  override_same_name                     = "true"
}
