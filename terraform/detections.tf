locals {
  detection_metric_namespace = "datasafe_audit"
  detection_alarm_window = {
    PT5M  = "5m"
    PT10M = "10m"
    PT15M = "15m"
    PT30M = "30m"
    PT1H  = "1h"
  }
  alarm_destinations = concat(
    var.notification_topic_ocids,
    var.create_notification_topic ? [oci_ons_notification_topic.database_risk[0].topic_id] : []
  )
  detections = jsondecode(file("${path.module}/detections.json"))
}

resource "oci_ons_notification_topic" "database_risk" {
  count          = var.create_notification_topic ? 1 : 0
  compartment_id = var.compartment_ocid
  name           = "${var.deployment_name}-database-risk"
  description    = "Destination for Data Safe audit detections and native baseline-drift events."
  freeform_tags  = local.tags
}

resource "oci_monitoring_alarm" "detection" {
  for_each                     = var.enable_detections && var.enable_alarms && length(local.alarm_destinations) > 0 ? local.detections : {}
  compartment_id               = var.compartment_ocid
  display_name                 = "${var.deployment_name} | ${each.value.title}"
  alarm_summary                = each.value.description
  body                         = "Review the Data Safe Audit | Detection & Baseline dashboard and investigate the matching Log Analytics records."
  destinations                 = local.alarm_destinations
  is_enabled                   = true
  metric_compartment_id        = var.compartment_ocid
  namespace                    = local.detection_metric_namespace
  resource_group               = var.deployment_name
  query                        = "${each.key}[${local.detection_alarm_window[var.detection_interval]}].max() > ${each.value.threshold}"
  severity                     = each.value.severity
  pending_duration             = "PT1M"
  repeat_notification_duration = "PT1H"
  freeform_tags                = local.tags
}

resource "oci_events_rule" "datasafe_baseline_drift" {
  count          = var.enable_datasafe_drift_events && length(local.alarm_destinations) > 0 ? 1 : 0
  compartment_id = var.data_safe_compartment_ocid
  display_name   = "${var.deployment_name}-datasafe-baseline-drift"
  description    = "Routes native Data Safe security and user assessment baseline drift."
  is_enabled     = true
  condition = jsonencode({
    eventType = [
      "com.oraclecloud.datasafe.securityassessmentdriftfrombaseline",
      "com.oraclecloud.datasafe.userassessmentdriftfrombaseline"
    ]
  })
  freeform_tags = local.tags

  actions {
    action {
      action_type = "ONS"
      is_enabled  = true
      topic_id    = local.alarm_destinations[0]
    }
  }
}
