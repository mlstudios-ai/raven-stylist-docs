output "execution_role_arn" {
  value = aws_iam_role.sagemaker_execution.arn
}

output "model_package_group_name" {
  value = aws_sagemaker_model_package_group.main.model_package_group_name
}

output "judge_inference_profile_id" {
  value = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
}
