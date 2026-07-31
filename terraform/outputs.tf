output "function_id" {
  value     = try(oci_functions_function.audit[0].id, null)
  sensitive = true
}

output "function_invoke_log_id" {
  value     = try(oci_logging_log.function_invoke[0].id, null)
  sensitive = true
}

output "logging_log_id" {
  value     = oci_logging_log.audit.id
  sensitive = true
}

output "logging_log_group_id" {
  value     = oci_logging_log_group.audit.id
  sensitive = true
}

output "cursor_bucket_name" {
  value = oci_objectstorage_bucket.cursor.name
}

output "service_connector_id" {
  value     = oci_sch_service_connector.audit.id
  sensitive = true
}

output "log_analytics_log_group_id" {
  value     = local.log_analytics_log_group_id
  sensitive = true
}

output "resource_schedule_id" {
  value     = try(oci_resource_scheduler_schedule.audit[0].id, null)
  sensitive = true
}

output "function_schedule" {
  value = {
    interval = var.schedule_interval
    cron     = local.effective_schedule_cron
  }
}

output "log_analytics_content" {
  value = try({
    fields  = oci_log_analytics_log_analytics_import_custom_content.audit[0].field_names
    parsers = oci_log_analytics_log_analytics_import_custom_content.audit[0].parser_names
    sources = oci_log_analytics_log_analytics_import_custom_content.audit[0].source_names
  }, null)
}

output "alarm_ids" {
  value     = { for key, item in oci_monitoring_alarm.detection : key => item.id }
  sensitive = true
}

output "notification_topic_id" {
  value     = try(oci_ons_notification_topic.database_risk[0].topic_id, null)
  sensitive = true
}
