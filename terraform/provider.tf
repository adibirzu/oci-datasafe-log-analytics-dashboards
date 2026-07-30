provider "oci" {
  config_file_profile = var.oci_profile
  region              = var.region
}

provider "oci" {
  alias               = "home"
  config_file_profile = var.oci_profile
  region              = data.oci_identity_regions.home.regions[0].name
}

data "oci_identity_tenancy" "current" {
  tenancy_id = var.tenancy_ocid
}

data "oci_identity_regions" "home" {
  filter {
    name   = "key"
    values = [data.oci_identity_tenancy.current.home_region_key]
  }
}
