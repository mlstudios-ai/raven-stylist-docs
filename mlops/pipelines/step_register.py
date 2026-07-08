"""
Register step — registers the trained model in SageMaker Model Registry with
PendingManualApproval status, writes a manifest, and closes the MLflow run.

When --model-s3-uri is provided (remote SageMaker execution), the model is
registered in the SageMaker Model Registry. Without it (local execution),
only the manifest is written.
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
import mlflow
from mlflow.tracking import MlflowClient
import yaml

from sigmoi.utils import get_logger

logger = get_logger("pipelines.step_register")


def _load_config() -> dict:
    for candidate in ("pipeline-config.yaml", "pipelines/pipeline-config.yaml"):
        p = Path(candidate)
        if p.exists():
            with p.open() as f:
                return yaml.safe_load(f)
    raise RuntimeError("pipeline-config.yaml not found")


def _sanitize_group_name(name: str) -> str:
    """SageMaker model package group names must be alphanumeric + hyphens."""
    return re.sub(r"[^a-zA-Z0-9-]", "-", name).strip("-")


def _ensure_model_package_group(sm, group_name: str, model_name: str) -> None:
    try:
        sm.create_model_package_group(
            ModelPackageGroupName=group_name,
            ModelPackageGroupDescription=f"Sigmoi AI Stylist model: {model_name}",
        )
        logger.info(f"Created model package group: {group_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConflictException":
            logger.info(f"Model package group already exists: {group_name}")
        else:
            raise


def _register_model(
    model_name: str,
    model_s3_uri: str,
    region: str,
    inference_image_uri: str,
    inference_instance_type: str,
) -> str:
    sm = boto3.client("sagemaker", region_name=region)
    group_name = _sanitize_group_name(model_name)
    _ensure_model_package_group(sm, group_name, model_name)

    response = sm.create_model_package(
        ModelPackageGroupName=group_name,
        ModelPackageDescription="Registered by sigmoi-mlops pipeline",
        InferenceSpecification={
            "Containers": [{
                "Image": inference_image_uri,
                "ModelDataUrl": model_s3_uri,
            }],
            "SupportedTransformInstanceTypes": [inference_instance_type],
            "SupportedRealtimeInferenceInstanceTypes": [inference_instance_type],
            "SupportedContentTypes": ["application/json"],
            "SupportedResponseMIMETypes": ["application/json"],
        },
        ModelApprovalStatus="PendingManualApproval",
    )

    arn = response["ModelPackageArn"]
    logger.info(f"Registered model version: {arn}")
    return arn


def main() -> None:
    config = _load_config()

    parser = argparse.ArgumentParser(description="Register model in SageMaker Model Registry")
    parser.add_argument("--model-path",  type=str, default=config["model-output-dir"])
    parser.add_argument("--model-name",  type=str, default=config["model-name"])
    parser.add_argument("--model-s3-uri", type=str, default=None,
                        help="S3 URI of model artifact — triggers SageMaker Model Registry registration")
    parser.add_argument("--metrics-dir", type=str, default=config["metrics-dir"])
    parser.add_argument("--inference-image-uri",     type=str, default=config.get("inference-image-uri"))
    parser.add_argument("--inference-instance-type", type=str, default=config.get("inference-instance-type"))
    parser.add_argument("--region",          type=str, default=config.get("region"))
    parser.add_argument("--tracking-run-id", type=str, default=None)
    args = parser.parse_args()

    os.environ.setdefault("MLFLOW_TRACKING_URI",    config["mlflow-tracking-uri"])
    os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", config["mlflow-experiment-name"])
    if args.tracking_run_id:
        os.environ.setdefault("MLFLOW_RUN_ID", args.tracking_run_id)

    model_package_arn = None

    if args.model_s3_uri:
        model_package_arn = _register_model(
            model_name=args.model_name,
            model_s3_uri=args.model_s3_uri,
            region=args.region,
            inference_image_uri=args.inference_image_uri,
            inference_instance_type=args.inference_instance_type,
        )
    else:
        logger.info("No --model-s3-uri provided — skipping SageMaker Model Registry")

    manifest = {
        "model_name": args.model_name,
        "model_path": args.model_path,
        "model_s3_uri": args.model_s3_uri,
        "model_package_arn": model_package_arn,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }

    manifest_path = Path(args.metrics_dir) / "registration.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Registration manifest saved to {manifest_path}")

    run_id = os.environ.get("MLFLOW_RUN_ID")
    client = MlflowClient()
    with mlflow.start_run(run_id=run_id):
        mlflow.set_tag("model_name", args.model_name)
        if model_package_arn:
            mlflow.set_tag("model_package_arn", model_package_arn)
    if run_id:
        client.set_terminated(run_id)
        logger.info(f"MLflow run {run_id} terminated")


if __name__ == "__main__":
    main()
