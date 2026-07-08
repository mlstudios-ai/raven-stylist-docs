output "bucket_name" {
  value = aws_s3_bucket.mlflow_artifacts.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.mlflow_artifacts.arn
}

output "tracking_arn" {
  description = "ARN of the SageMaker MLflow App"
  value       = aws_sagemaker_mlflow_app.main.arn
}

output "tracking_uri" {
  description = "URI of the SageMaker MLFLow app"
  value       = aws_sagemaker_mlflow_app.main.arn
}