variable "project" { type = string }
variable "environment" { type = string }

variable "ecr_repository_arn" {
  description = "ARN of the ECR repository to push the built image to"
  type        = string
}

variable "ecr_repository_url" {
  description = "URL of the ECR repository (without tag)"
  type        = string
}

variable "github_repo_url" {
  description = "HTTPS URL of the GitHub repository"
  type        = string
}

variable "github_token_ssm_path" {
  description = "SSM Parameter Store path for the GitHub personal access token"
  type        = string
  default     = "/sigmoi/github/token"
}
