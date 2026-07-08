data "aws_ssm_parameter" "github_token" {
  name            = var.github_token_ssm_path
  with_decryption = true
}

resource "aws_codebuild_source_credential" "github" {
  auth_type   = "PERSONAL_ACCESS_TOKEN"
  server_type = "GITHUB"
  token       = data.aws_ssm_parameter.github_token.value
}

# ── IAM role for CodeBuild ────────────────────────────────────────────────────

resource "aws_iam_role" "codebuild" {
  name = "${var.project}-codebuild-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codebuild.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "codebuild_ecr" {
  name = "ecr-push"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ]
        Resource = [var.ecr_repository_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = ["*"]
      }
    ]
  })
}

resource "aws_iam_role_policy" "codebuild_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
      ]
      Resource = ["*"]
    }]
  })
}

# ── CodeBuild project ─────────────────────────────────────────────────────────

resource "aws_codebuild_project" "base_image" {
  name          = "${var.project}-base-image-build"
  description   = "Builds and pushes the sigmoi base Docker image to ECR"
  service_role  = aws_iam_role.codebuild.arn
  build_timeout = 60

  source {
    type            = "GITHUB"
    location        = var.github_repo_url
    git_clone_depth = 1
    buildspec       = "docker/buildspec.yml"
  }

  environment {
    compute_type    = "BUILD_GENERAL1_LARGE"
    image           = "aws/codebuild/standard:7.0"
    type            = "LINUX_CONTAINER"
    privileged_mode = true

    environment_variable {
      name  = "ECR_REGISTRY"
      value = split("/", var.ecr_repository_url)[0]
    }

    environment_variable {
      name  = "ECR_REPO_URL"
      value = var.ecr_repository_url
    }
  }

  artifacts {
    type = "NO_ARTIFACTS"
  }

  logs_config {
    cloudwatch_logs {
      group_name  = "/aws/codebuild/${var.project}-base-image-build"
      stream_name = "build"
    }
  }

  depends_on = [aws_codebuild_source_credential.github]
}

# ── Webhook: auto-trigger on docker/ changes to main ─────────────────────────

resource "aws_codebuild_webhook" "docker" {
  project_name = aws_codebuild_project.base_image.name
  build_type   = "BUILD"

  filter_group {
    filter {
      type    = "EVENT"
      pattern = "PUSH"
    }
    filter {
      type    = "HEAD_REF"
      pattern = "refs/heads/main"
    }
    filter {
      type    = "FILE_PATH"
      pattern = "docker/.*"
    }
  }
}
