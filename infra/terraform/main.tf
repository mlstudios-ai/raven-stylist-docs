module "s3" {
  source      = "./modules/s3"
  project     = var.project
  environment = var.environment
}

module "ecr" {
  source      = "./modules/ecr"
  project     = var.project
  environment = var.environment
}

module "codebuild" {
  source              = "./modules/codebuild"
  project             = var.project
  environment         = var.environment
  ecr_repository_arn  = module.ecr.repository_arn
  ecr_repository_url  = module.ecr.repository_url
  github_repo_url     = "https://github.com/mlstudios-ai/sigmoi-mlops.git"
}

import {
  id = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
  to = module.oidc.aws_iam_openid_connect_provider.github
}

module "oidc" {
  source                = "./modules/oidc"
  project               = var.project
  account_id            = data.aws_caller_identity.current.account_id
  github_org            = "mlstudios-ai"
  github_repo           = "sigmoi-mlops"
  codebuild_project_arn = module.codebuild.project_arn
  pipeline_name         = "sigmoi-stylist"
}

module "mlflow" {
  source      = "./modules/mlflow"
  project     = var.project
  environment = var.environment
}

module "sagemaker" {
  source               = "./modules/sagemaker"
  project              = var.project
  environment          = var.environment
  artifact_bucket_arn  = module.s3.artifact_bucket_arn
  mlflow_bucket_arn    = module.mlflow.bucket_arn
  mlflow_arn           = module.mlflow.tracking_arn
  ecr_repository_arn   = module.ecr.repository_arn
}
