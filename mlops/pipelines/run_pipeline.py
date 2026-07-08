import argparse
import os
import subprocess
import yaml
import boto3
import mlflow
from mlflow.tracking import MlflowClient
from datetime import datetime
from pathlib import Path
from sigmoi.utils import get_logger

logger = get_logger("run_pipeline")

config_file = Path("pipeline-config.yaml")
if not config_file.exists():
    config_file = Path("pipelines/pipeline-config.yaml")

if not config_file.exists():
    raise RuntimeError("pipeline-config.yaml not found in expected locations.")

with config_file.open("r") as f:
    config = yaml.safe_load(f)


def _generate_run_suffix() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"]).decode().strip()
        if dirty:
            logger.warning("Working tree has uncommitted changes — run may not be fully reproducible")
    except subprocess.CalledProcessError:
        git_hash = "nogit"
    return f"{timestamp}-{git_hash}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-name",     type=str, default=config["pipeline-name"])
    parser.add_argument("--pipeline-run-name", type=str, default=None, help="Override generated pipeline run name")
    parser.add_argument("--remote", action="store_true", help="Run on SageMaker (default: run locally)")
    parser.add_argument("--no-start", action="store_true", help="Upsert pipeline definition only, do not start an execution")
    # remote-only args
    parser.add_argument("--bucket", type=str, default=config["bucket-name"])
    parser.add_argument("--prefix", type=str, default=config["bucket-prefix"])
    parser.add_argument("--region", type=str, default=config["region"])
    parser.add_argument("--role",   type=str, default=config["role"])
    args = parser.parse_args()

    pipeline_name = args.pipeline_name or os.environ.get("PIPELINE_NAME")

    run_suffix        = _generate_run_suffix()
    pipeline_run_name = args.pipeline_run_name or f"{config['pipeline-run-prefix']}-{run_suffix}"
    mlflow_run_name   = pipeline_run_name #f"{config['mlflow-run-prefix']}-{run_suffix}"

    mlflow.set_tracking_uri(config["mlflow-tracking-uri"])
    experiment = mlflow.set_experiment(config["mlflow-experiment-name"])
    client = MlflowClient()
    tracking_run = client.create_run(
        experiment_id=experiment.experiment_id,
        run_name=mlflow_run_name,
    )
    tracking_run_id = tracking_run.info.run_id

    logger.info(f"Pipeline run:   {pipeline_run_name}")
    logger.info(f"MLflow run:     {mlflow_run_name}  ({tracking_run_id})")
    logger.info(f"Remote:         {args.remote}")

    config["pipeline-name"] = pipeline_name

    if args.remote:
        from sagemaker.core.helper.session_helper import Session
        from sm_pipeline import build_pipeline

        bucket = args.bucket or os.environ.get("SIGMOI_BUCKET_NAME")
        prefix = args.prefix or os.environ.get("SIGMOI_MLOPS_BUCKET_PREFIX")
        region = args.region or os.environ.get("AWS_REGION")
        role   = args.role   or os.environ.get("SAGEMAKER_ROLE_ARN")

        config["bucket-name"]   = bucket
        config["bucket-prefix"] = prefix
        config["region"]        = region
        config["role"]          = role

        session = Session(
            boto_session=boto3.Session(
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=region
            ),
            default_bucket=bucket,
            default_bucket_prefix=prefix
        )

        pipeline = build_pipeline(
            name=pipeline_name,
            session=session,
            role=role,
            config=config,
            pipeline_run_name=pipeline_run_name,
            tracking_run_id=tracking_run_id,
            run_local=False
        )
        pipeline.upsert(role_arn=role)
        if not args.no_start:
            pipeline.start(parameters={"pipeline_run_name": pipeline_run_name})

    else:
        from local_pipeline import build_pipeline

        os.environ["MLFLOW_RUN_ID"] = tracking_run_id

        pipeline = build_pipeline(
            name=pipeline_name,
            config=config,
            pipeline_run_name=pipeline_run_name,
        )
        pipeline.upsert()
        if not args.no_start:
            pipeline.start()
