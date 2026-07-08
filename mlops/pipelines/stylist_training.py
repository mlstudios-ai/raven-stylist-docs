"""
Sigmoi AI stylist — SageMaker Pipeline definition.

Wires together: ingest → extract → engineer → transform → preprocess → train → evaluate → register

Run locally:   uv run python pipelines/stylist_training.py --run-local
Submit to AWS: uv run python pipelines/stylist_training.py --submit
"""
import argparse
import os

import sagemaker
from sagemaker.train import ModelTrainer
from sagemaker.train.configs import Compute, InputData
from sagemaker.train.configs import SourceCode
from sagemaker.core.shapes.processing import ProcessingInput, ProcessingOutput
from sagemaker.core.processing import SKLearnProcessor
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.fail_step import FailStep
from sagemaker.workflow.functions import JsonGet
from sagemaker.workflow.parameters import ParameterFloat, ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

from pipelines.sagemaker.core import engineer, evaluate, extract, ingest, preprocess, register, train

# ── Pipeline parameters (overridable at runtime) ────────────────────────────

param_instance_type_processing = ParameterString(
    name="ProcessingInstanceType", default_value="ml.t3.medium"
)
param_instance_type_training = ParameterString(
    name="TrainingInstanceType", default_value="ml.m5.large"
)
param_training_image_uri = ParameterString(
    name="TrainingImageUri", default_value=""
)
param_model_name = ParameterString(
    name="ModelName", default_value="unsloth/Qwen2.5-7B-Instruct"
)
param_val_size = ParameterFloat(name="ValSize", default_value=0.1)
param_test_size = ParameterFloat(name="TestSize", default_value=0.1)
param_random_seed = ParameterInteger(name="RandomSeed", default_value=42)
param_accuracy_threshold = ParameterFloat(name="AccuracyThreshold", default_value=0.75)
param_experiment_name = ParameterString(
    name="ExperimentName", default_value="sigmoi-stylist-training"
)


_ENTRYPOINT = "pipelines/processing_entrypoint.py"
_SOURCE_DIR = "."


def build_pipeline(
    role: str,
    bucket: str,
    mlflow_tracking_uri: str,
    training_image_uri: str,
    region: str = "ap-southeast-2",
    pipeline_name: str = "sigmoi-stylist-training",
) -> Pipeline:
    session = PipelineSession(boto_session=sagemaker.Session().boto_session)

    processor = SKLearnProcessor(
        framework_version="1.2-1",
        instance_type=param_instance_type_processing,
        instance_count=1,
        role=role,
        sagemaker_session=session,
        env={"MLFLOW_TRACKING_URI": mlflow_tracking_uri},
    )

    # ── Step 1: Ingest ───────────────────────────────────────────────────────
    step_ingest = ProcessingStep(
        name="Ingest",
        step_args=processor.run(
            inputs=[
                ProcessingInput(
                    source=f"s3://{bucket}/data/external",
                    destination="/opt/ml/processing/input",
                )
            ],
            outputs=[
                ProcessingOutput(output_name="raw", source="/opt/ml/processing/raw")
            ],
            code=_ENTRYPOINT,
            source_dir=_SOURCE_DIR,
            arguments=["pipelines/steps/ingest.py"],
        ),
    )

    # ── Step 2: Extract ──────────────────────────────────────────────────────
    step_extract = ProcessingStep(
        name="Extract",
        step_args=processor.run(
            inputs=[
                ProcessingInput(
                    source=step_ingest.properties.ProcessingOutputConfig.Outputs["raw"].S3Output.S3Uri,
                    destination="/opt/ml/processing/raw",
                ),
                ProcessingInput(
                    source=f"s3://{bucket}/config/templates",
                    destination="/opt/ml/processing/config",
                ),
            ],
            outputs=[
                ProcessingOutput(output_name="features", source="/opt/ml/processing/features")
            ],
            code=_ENTRYPOINT,
            source_dir=_SOURCE_DIR,
            arguments=["pipelines/steps/extract.py"],
        ),
    )

    # ── Step 3: Engineer ─────────────────────────────────────────────────────
    step_engineer = ProcessingStep(
        name="Engineer",
        step_args=processor.run(
            inputs=[
                ProcessingInput(
                    source=step_extract.properties.ProcessingOutputConfig.Outputs["features"].S3Output.S3Uri,
                    destination="/opt/ml/processing/features",
                )
            ],
            outputs=[
                ProcessingOutput(output_name="engineered", source="/opt/ml/processing/engineered")
            ],
            code=_ENTRYPOINT,
            source_dir=_SOURCE_DIR,
            arguments=["pipelines/steps/engineer.py"],
        ),
    )

    # ── Step 4: Transform ────────────────────────────────────────────────────
    step_transform = ProcessingStep(
        name="Transform",
        step_args=processor.run(
            inputs=[
                ProcessingInput(
                    source=step_engineer.properties.ProcessingOutputConfig.Outputs["engineered"].S3Output.S3Uri,
                    destination="/opt/ml/processing/features",
                ),
                ProcessingInput(
                    source=f"s3://{bucket}/config/templates",
                    destination="/opt/ml/processing/templates",
                ),
            ],
            outputs=[
                ProcessingOutput(output_name="dataset", source="/opt/ml/processing/dataset")
            ],
            code=_ENTRYPOINT,
            source_dir=_SOURCE_DIR,
            arguments=["pipelines/steps/transform.py"],
        ),
    )

    # ── Step 5: Preprocess ───────────────────────────────────────────────────
    step_preprocess = ProcessingStep(
        name="Preprocess",
        step_args=processor.run(
            inputs=[
                ProcessingInput(
                    source=step_transform.properties.ProcessingOutputConfig.Outputs["dataset"].S3Output.S3Uri,
                    destination="/opt/ml/processing/dataset",
                )
            ],
            outputs=[
                ProcessingOutput(output_name="tokenized", source="/opt/ml/processing/tokenized")
            ],
            code=_ENTRYPOINT,
            source_dir=_SOURCE_DIR,
            arguments=[
                "pipelines/steps/preprocess.py",
                "--val-size", param_val_size,
                "--test-size", param_test_size,
                "--seed", param_random_seed,
            ],
            environment={"SIGMOI_MODEL_NAME": param_model_name},
        ),
    )

    # ── Step 6: Train ────────────────────────────────────────────────────────
    model_trainer = ModelTrainer(
        training_image=param_training_image_uri,
        compute=Compute(
            instance_type=param_instance_type_training,
            instance_count=1,
        ),
        source_code=SourceCode(
            source_dir=_SOURCE_DIR,
            entry_script="pipelines/steps/train.py",
        ),
        s3_output_path=f"s3://{bucket}/models",
        role=role,
        sagemaker_session=session,
        environment={
            "MLFLOW_TRACKING_URI": mlflow_tracking_uri,
            "MLFLOW_EXPERIMENT_NAME": param_experiment_name,
            "SIGMOI_MODEL_NAME": param_model_name,
        },
        input_data_config=[
            InputData(
                channel_name="dataset",
                data_source=step_preprocess.properties.ProcessingOutputConfig.Outputs["tokenized"].S3Output.S3Uri,
            )
        ],
    )

    step_train = TrainingStep(
        name="Train",
        step_args=model_trainer.train(),
    )

    # ── Step 7: Evaluate ─────────────────────────────────────────────────────
    evaluation_report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )

    step_evaluate = ProcessingStep(
        name="Evaluate",
        step_args=processor.run(
            inputs=[
                ProcessingInput(
                    source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                    destination="/opt/ml/processing/model",
                ),
                ProcessingInput(
                    source=step_preprocess.properties.ProcessingOutputConfig.Outputs["tokenized"].S3Output.S3Uri,
                    destination="/opt/ml/processing/dataset",
                ),
            ],
            outputs=[
                ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/metrics")
            ],
            code=_ENTRYPOINT,
            source_dir=_SOURCE_DIR,
            arguments=[
                "pipelines/steps/evaluate.py",
                "--threshold", param_accuracy_threshold,
            ],
            environment={"MLFLOW_TRACKING_URI": mlflow_tracking_uri},
        ),
        property_files=[evaluation_report],
    )

    # ── Step 8: Quality gate + Register ──────────────────────────────────────
    step_register = ProcessingStep(
        name="Register",
        step_args=processor.run(
            inputs=[
                ProcessingInput(
                    source=step_evaluate.properties.ProcessingOutputConfig.Outputs["evaluation"].S3Output.S3Uri,
                    destination="/opt/ml/processing/metrics",
                )
            ],
            code=_ENTRYPOINT,
            source_dir=_SOURCE_DIR,
            arguments=[
                "pipelines/steps/register.py",
                "--mlflow-tracking-uri", mlflow_tracking_uri,
            ],
        ),
    )

    step_fail = FailStep(
        name="QualityGateFailed",
        error_message=JsonGet(
            step_name=step_evaluate.name,
            property_file=evaluation_report,
            json_path="similarity_results.accuracy",
        ),
    )

    step_cond = ConditionStep(
        name="CheckAccuracy",
        conditions=[
            ConditionGreaterThanOrEqualTo(
                left=JsonGet(
                    step_name=step_evaluate.name,
                    property_file=evaluation_report,
                    json_path="similarity_results.accuracy",
                ),
                right=param_accuracy_threshold,
            )
        ],
        if_steps=[step_register],
        else_steps=[step_fail],
    )

    pipeline = Pipeline(
        name=pipeline_name,
        parameters=[
            param_instance_type_processing,
            param_instance_type_training,
            param_training_image_uri,
            param_model_name,
            param_val_size,
            param_test_size,
            param_random_seed,
            param_accuracy_threshold,
            param_experiment_name,
        ],
        steps=[
            step_ingest,
            step_extract,
            step_engineer,
            step_transform,
            step_preprocess,
            # step_train,
            # step_evaluate,
            # step_cond,
        ],
        sagemaker_session=session,
    )


def run_local() -> None:
    """Run each step sequentially in-process for local development."""
    from pipelines.sagemaker.core import transform
    import sys

    from sigmoi.utils import get_logger
    logger = get_logger("pipeline.local")

    logger.info("── Step 1: Ingest ──────────────────────────────────────────────")
    sys.argv = ["ingest", "--input-path", "data/external", "--output-path", "data/raw"]
    ingest.main()

    logger.info("── Step 2: Extract ─────────────────────────────────────────────")
    sys.argv = ["extract", "--input-path", "data/raw", "--schema-path", "config/templates", "--output-path", "data/processed/features"]
    extract.main()

    logger.info("── Step 3: Engineer ────────────────────────────────────────────")
    sys.argv = ["engineer", "--input-path", "data/processed/features", "--output-path", "data/processed/engineered"]
    engineer.main()

    logger.info("── Step 4: Transform ───────────────────────────────────────────")
    sys.argv = ["transform", "--input-path", "data/processed/engineered", "--template-path", "config/templates", "--output-dataset-file", "data/processed/transformed/dataset.jsonl"]
    transform.main()

    logger.info("── Step 5: Preprocess ──────────────────────────────────────────")
    sys.argv = ["preprocess", "--dataset_file", "data/processed/transformed/dataset.jsonl", "--output-path", "data/processed/tokenized"]
    preprocess.main()

    logger.info("── Step 6: Train ───────────────────────────────────────────────")
    sys.argv = ["train", "--dataset-path", "data/processed/tokenized", "--model-output-dir", "models/output", "--model-best-dir", "models/best"]
    train.main()

    logger.info("── Step 7: Evaluate ────────────────────────────────────────────")
    sys.argv = ["evaluate", "--model-path", "models/best", "--dataset-path", "data/processed/tokenized", "--output-path", "reports"]
    evaluate.main()

    logger.info("── Step 8: Register ────────────────────────────────────────────")
    sys.argv = ["register", "--model-path", "models/best", "--metrics-path", "reports/evaluation.json"]
    register.main()

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-local", action="store_true", help="Run pipeline locally without SageMaker")
    parser.add_argument("--submit", action="store_true", help="Submit pipeline to SageMaker")
    parser.add_argument("--role", type=str, default=os.environ.get("SAGEMAKER_ROLE_ARN"))
    parser.add_argument("--bucket", type=str, default=os.environ.get("SIGMOI_ARTIFACT_BUCKET"))
    parser.add_argument("--prefix", type=str, default=os.environ.get("SIGMOI_BUcKET_PREFIX"))
    parser.add_argument("--mlflow-uri", type=str, default=os.environ.get("MLFLOW_TRACKING_URI"))
    parser.add_argument("--training-image-uri", type=str, default=os.environ.get("TRAINING_IMAGE_URI"))
    args = parser.parse_args()

    if args.run_local:
        run_local()
    elif args.submit:
        pipeline = build_pipeline(
            role=args.role,
            bucket=args.bucket+"/"+args.prefix,
            mlflow_tracking_uri=args.mlflow_uri,
            training_image_uri=args.training_image_uri,
        )
        pipeline.upsert(role_arn=args.role)
        execution = pipeline.start()
        print(f"Pipeline submitted — execution ARN: {execution.arn}")
    else:
        parser.print_help()
