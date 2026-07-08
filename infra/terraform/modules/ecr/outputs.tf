output "repository_url" {
  description = "ECR repository URL — use this as the training_image in ModelTrainer"
  value       = aws_ecr_repository.base_image.repository_url
}

output "repository_arn" {
  description = "ECR repository ARN"
  value       = aws_ecr_repository.base_image.arn
}

output "registry_id" {
  description = "AWS account ID owning the registry"
  value       = aws_ecr_repository.base_image.registry_id
}
