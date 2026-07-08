# SageMaker setup
output "artifact_bucket_name" {
  description = "S3 bucket for sagemaker artifacts and data"
  value       = module.s3.artifact_bucket_name
}

output "sagemaker_execution_role_arn" {
  description = "IAM role ARN for SageMaker"
  value       = module.sagemaker.execution_role_arn
}

# Serverless MLFLow app setup
output "mlflow_bucket_name" {
  description = "S3 bucket for MLflow artifacts"
  value       = module.mlflow.bucket_name
}

output "mlflow_tracking_arn" {
  description = "ARN of the SageMaker MLflow App"
  value       = module.mlflow.tracking_arn
}

output "mlflow_tracking_uri" {
  description = "URI of the SageMaker MLflow App"
  value       = module.mlflow.tracking_uri
}

# ECR
output "base_image_repository_url" {
  description = "ECR repository URL for the sigmoi base image — use as training_image in ModelTrainer"
  value       = module.ecr.repository_url
}

# CodeBuild
output "codebuild_project_name" {
  description = "CodeBuild project name for manual builds"
  value       = module.codebuild.project_name
}

# GitHub Actions OIDC
output "github_actions_role_arn" {
  description = "IAM role ARN to set as AWS_ROLE_ARN secret in GitHub"
  value       = module.oidc.role_arn
}