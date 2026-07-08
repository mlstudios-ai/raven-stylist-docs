variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-2"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["prod", "staging", "dev"], var.environment)
    error_message = "Environment must be one of 'prod', 'staging', or 'dev'."
  }
}

variable "project" {
  description = "Project name"
  type        = string
  default     = "sigmoi"
}

variable "sagemaker_instance_type_training" {
  description = "SageMaker training instance type"
  type        = string
  default     = "ml.m5.large"
}

variable "sagemaker_instance_type_endpoint" {
  description = "SageMaker endpoint instance type"
  type        = string
  default     = "ml.t2.medium"
}
