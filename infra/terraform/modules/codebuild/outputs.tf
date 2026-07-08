output "project_name" {
  description = "CodeBuild project name"
  value       = aws_codebuild_project.base_image.name
}

output "project_arn" {
  description = "CodeBuild project ARN"
  value       = aws_codebuild_project.base_image.arn
}
