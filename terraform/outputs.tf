output "function_id" {
  value     = try(oci_functions_function.audit[0].id, null)
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

output "resource_schedule_id" {
  value     = try(oci_resource_scheduler_schedule.audit[0].id, null)
  sensitive = true
}
