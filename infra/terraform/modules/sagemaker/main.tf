resource "aws_iam_role" "sagemaker_execution" {
  name = "${var.project}-sagemaker-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_full" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_iam_role_policy" "sagemaker_s3" {
  name = "s3-artifact-access"
  role = aws_iam_role.sagemaker_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [var.artifact_bucket_arn, "${var.artifact_bucket_arn}/*"]
      }
    ]
  })
}

resource "aws_iam_role_policy" "sagemaker_mlflow" {                                                                                  
  name = "mlflow-app-access"                           
  role = aws_iam_role.sagemaker_execution.id                                                                                            
                                                                                                                                        
  policy = jsonencode({
    Version = "2012-10-17"                                                                                                              
    Statement = [
      {
        # Permission to talk to the MLflow App
        Action   = ["sagemaker:CallMlflowAppApi", "sagemaker-mlflow:*"]
        Effect   = "Allow"
        Resource = [var.mlflow_arn]
      },
      {        
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [var.mlflow_bucket_arn, "${var.mlflow_bucket_arn}/*"]                                                                  
    }]                                                                                                                                  
  })                                                                                                                                    
}     

resource "aws_iam_role_policy" "sagemaker_ecr" {
  name = "ecr-base-image-pull"
  role = aws_iam_role.sagemaker_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
        ]
        Resource = [var.ecr_repository_arn]
      },
      {
        # GetAuthorizationToken is not resource-scoped
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = ["*"]
      }
    ]
  })
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  judge_inference_profile_arn = "arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:inference-profile/apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
}

resource "aws_iam_role_policy" "sagemaker_bedrock" {
  name = "bedrock-judge-access"
  role = aws_iam_role.sagemaker_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = [local.judge_inference_profile_arn]
      }
    ]
  })
}

# SageMaker Model Registry (uses default MLflow model name)
resource "aws_sagemaker_model_package_group" "main" {
  model_package_group_name        = "${var.project}-${var.environment}"
  model_package_group_description = "AI Stylist model for ${var.project}"
}
