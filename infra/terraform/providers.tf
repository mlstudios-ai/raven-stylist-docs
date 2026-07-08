terraform {
  required_version = ">= 1.12.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.35.0"
    }
  }

  backend "s3" {
    bucket = "sigmoi-terraform-state"
    key    = "sigmoi-mlops/terraform.tfstate"
    region = "ap-southeast-2"
    encrypt = true
  }
}

data "aws_caller_identity" "current" {}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "sigmoi-mlops"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}