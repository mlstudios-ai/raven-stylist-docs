variable "project" { type = string }
variable "account_id" { type = string }

variable "github_org" {
  description = "GitHub organisation or user owning the repo"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

variable "codebuild_project_arn" {
  description = "ARN of the CodeBuild project GH Actions is allowed to trigger"
  type        = string
}

variable "pipeline_name" {
  description = "SageMaker pipeline name GH Actions is allowed to start"
  type        = string
}
