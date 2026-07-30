resource "oci_identity_dynamic_group" "function" {
  count          = var.create_iam_resources && var.deploy_function ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = replace("${var.deployment_name}-function", "-", "_")
  description    = "Resource principal for the Data Safe audit export function."
  matching_rule  = "ALL {resource.id = '${oci_functions_function.audit[0].id}'}"
  freeform_tags  = local.tags
}

resource "oci_identity_dynamic_group" "scheduler" {
  count          = var.create_iam_resources && var.deploy_function ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = replace("${var.deployment_name}-scheduler", "-", "_")
  description    = "Resource Scheduler principals scoped to the solution compartment."
  matching_rule  = "ALL {resource.type = 'resourceschedule', resource.compartment.id = '${var.compartment_ocid}'}"
  freeform_tags  = local.tags
}

resource "oci_identity_policy" "function" {
  count          = var.create_iam_resources && var.deploy_function ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = replace("${var.deployment_name}-function-policy", "-", "_")
  description    = "Least-privilege Data Safe audit export permissions."
  freeform_tags  = local.tags
  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.function[0].name} to read data-safe-audit-events in compartment id ${var.data_safe_compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.function[0].name} to use log-content in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.function[0].name} to manage objects in compartment id ${var.compartment_ocid} where target.bucket.name='${oci_objectstorage_bucket.cursor.name}'",
    "Allow dynamic-group ${oci_identity_dynamic_group.function[0].name} to read objectstorage-namespaces in tenancy",
  ]
}

resource "oci_identity_policy" "scheduler" {
  count          = var.create_iam_resources && var.deploy_function ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = replace("${var.deployment_name}-scheduler-policy", "-", "_")
  description    = "Allow Resource Scheduler to invoke only compartment functions."
  freeform_tags  = local.tags
  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.scheduler[0].name} to use functions-family in compartment id ${var.compartment_ocid}",
  ]
}

resource "oci_identity_policy" "connector" {
  count          = var.create_iam_resources ? 1 : 0
  provider       = oci.home
  compartment_id = var.tenancy_ocid
  name           = replace("${var.deployment_name}-connector-policy", "-", "_")
  description    = "Allow this Connector Hub flow to read OCI Logging and write its Log Analytics group."
  freeform_tags  = local.tags
  statements = [
    "Allow any-user to read log-content in compartment id ${var.compartment_ocid} where all {request.principal.type='serviceconnector', request.principal.compartment.id='${var.compartment_ocid}'}",
    "Allow any-user to use loganalytics-log-group in compartment id ${var.compartment_ocid} where all {request.principal.type='serviceconnector', target.loganalytics-log-group.id='${local.log_analytics_log_group_id}', request.principal.compartment.id='${var.compartment_ocid}'}",
  ]
}
