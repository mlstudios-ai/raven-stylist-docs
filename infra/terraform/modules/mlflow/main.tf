# 1. S3 Bucket for Models/Artifacts
resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket = "${var.project}-mlflow-artifacts-${var.environment}"
}

resource "aws_s3_bucket_versioning" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "mlflow_artifacts" {
  bucket                  = aws_s3_bucket.mlflow_artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 2. IAM Role for MLflow to talk to S3
resource "aws_iam_role" "mlflow_role" {
  name = "${var.project}-mlflow-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
    }]
  })
}

# 3. Attach Permissions (S3 + MLflow API)
resource "aws_iam_role_policy" "mlflow_policy" {
  role = aws_iam_role.mlflow_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"]
        Effect = "Allow"
        Resource = ["${aws_s3_bucket.mlflow_artifacts.arn}", "${aws_s3_bucket.mlflow_artifacts.arn}/*"]
      },
      {
        Action = ["sagemaker-mlflow:*", "sagemaker:CallMlflowAppApi"]
        Effect = "Allow"
        Resource = "*"
      }
    ]
  })
}

# 4. The Serverless MLflow App
resource "aws_sagemaker_mlflow_app" "main" {
  name               = "${var.project}-${var.environment}"
  artifact_store_uri = "s3://${aws_s3_bucket.mlflow_artifacts.bucket}"
  role_arn           = aws_iam_role.mlflow_role.arn
}
