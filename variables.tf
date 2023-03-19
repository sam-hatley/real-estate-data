locals {
  data_lake_bucket = "data_lake"
}

variable "project" {
  description = "real-estate-data"
  default     = "real-estate-data-377813"
}

variable "region" {
  description = "Region for GCP resources. Choose as per your location: https://cloud.google.com/about/locations"
  default     = "europe-west2"
  type        = string
}

variable "storage_class" {
  description = "Storage class type for bucket."
  default     = "STANDARD"
}

variable "RM_DATASET" {
  description = "BigQuery Dataset that raw data from GSC will be written to"
  type        = string
  default     = "rm_data"
}
