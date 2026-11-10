variable "aws_region" {
  description = "AWS deployment region. No deployment occurs during local validation."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Lowercase project name used for resource naming."
  type        = string
  default     = "task-api"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name must be 3-21 lowercase letters, digits, or hyphens and start with a letter."
  }
}

variable "lambda_artifact_path" {
  description = "Path to a prebuilt Lambda zip with task_api and runtime dependencies."
  type        = string
  default     = "../dist/task_api.zip"
}

variable "cognito_domain_prefix" {
  description = "Globally unique Amazon Cognito managed-login domain prefix."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", var.cognito_domain_prefix))
    error_message = "cognito_domain_prefix must be 1-63 lowercase alphanumeric characters or hyphens, starting and ending alphanumeric."
  }
}

variable "cognito_callback_urls" {
  description = "OAuth authorization-code callback URLs; replace the local placeholder before deployment."
  type        = list(string)
  default     = ["https://localhost/callback"]
}

variable "cognito_logout_urls" {
  description = "Managed-login logout URLs; replace the local placeholder before deployment."
  type        = list(string)
  default     = ["https://localhost/logout"]
}

variable "log_retention_days" {
  description = "CloudWatch retention for API and Lambda logs."
  type        = number
  default     = 30
  validation {
    condition     = contains([7, 14, 30, 60, 90, 120, 150, 180, 365], var.log_retention_days)
    error_message = "Choose a supported log retention period."
  }
}
