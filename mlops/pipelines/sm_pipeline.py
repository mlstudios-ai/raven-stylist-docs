import os
from pathlib import Path

import boto3
from sagemaker.train import ModelTrainer
from sagemaker.train.configs import InputData, SourceCode, Compute, StoppingCondition
from sagemaker.mlops.workflow.pipeline import Pipeline, ExecutionVariables
from sagemaker.core.workflow.parameters import ParameterString
from sagemaker.mlops.local import LocalPipelineSession
from sagemaker.core.processing import FrameworkProcessor, Processor
from sagemaker.core.helper.session_helper import Session
from sagemaker.core.workflow.pipeline_context import PipelineSession
from sagemaker.core.workflow import Join
from sagemaker.mlops.workflow.steps import (
    CacheConfig,
    ProcessingStep,
    TrainingStep
)
from sagemaker.core.shapes import (
    ProcessingInput,
    ProcessingS3Input,
    ProcessingOutput,
    ProcessingS3Output,
    OutputDataConfig,
    CheckpointConfig
)

def build_pipeline(
    name: str,
    session: Session,
    role: str,
    config: dict,
    pipeline_run_name,
    tracking_run_id,
    run_local: False
):
    # initialize storage locations
    bucket_name = session.default_bucket()
    bucket_prefix = session.default_bucket_prefix
    bucket_uri = f"s3://{bucket_name}/{bucket_prefix}"
    cache_config = CacheConfig(enable_caching=True, expire_after="30d")
    pipeline_session = LocalPipelineSession(boto_session=session.boto_session, disable_local_code=False) if run_local else PipelineSession(boto_session=session.boto_session)
    
    ############# PROCESSING ###############
    processing_instance_type    = config["processing-instance-type"]
    processing_instance_count   = config["processing-instance-count"]
    processing_image_uri        = config["processing-image-uri"]
    
    # initialise processor
    processor = FrameworkProcessor(
        image_uri=processing_image_uri,
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        sagemaker_session=pipeline_session,
        role=role
    )
    
    # initialise processing variables    
    input_dir                   = config["external-dir"]
    raw_dir                     = config["raw-dir"]
    schema_dir                  = config["schema-dir"]
    extract_dir                 = config["extract-dir"]
    feature_dir                 = config["feature-dir"]
    template_dir                = config["template-dir"]
    dataset_file_path           = config["dataset-file-path"]
    dataset_path                = Path(dataset_file_path)
    full_dataset_dir            = dataset_path.parent.as_posix()
    full_dataset_file           = dataset_path.name
    val_size                    = config["split-val-size"]
    test_size                   = config["split-test-size"]
    seed                        = config["split-seed"]
    split_dir                   = config["dataset-split-dir"]
    format_dir                  = config["dataset-formatted-dir"]
    token_dir                   = config["dataset-tokenized-dir"]
    max_seq_length              = config["max-seq-length"]
    base_model_name             = config["base-model-name"]
    sm_processing_input_dir     = "/opt/ml/processing/input"
    sm_processing_output_dir    = "/opt/ml/processing/out"
    
    # ---------- STEP 0: Initialise Environment  --------------- # 
    # pipeline data folders to copy for this run
    #   configs/
    #   data/
    
    source_uri=f"{bucket_uri}"
    run_uri = f"{bucket_uri}/runs"
    run_id = ParameterString(name="pipeline_run_name", default_value=pipeline_run_name)
    
    config_data_dir = "configs"
    source_data_dir = "data"
    
    step_init = ProcessingStep(
        name="Init",
        cache_config=cache_config,
        step_args=processor.run(
            inputs=[                
                ProcessingInput(
                    input_name="configs_data",
                    s3_input=ProcessingS3Input(
                        s3_uri=f"{source_uri}/{config_data_dir}",
                        local_path=f"{sm_processing_input_dir}/{config_data_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                ),            
                ProcessingInput(
                    input_name="source_data",
                    s3_input=ProcessingS3Input(
                        s3_uri=f"{source_uri}/{source_data_dir}",
                        local_path=f"{sm_processing_input_dir}/{source_data_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                )
            ],
            outputs=[
                ProcessingOutput(
                    output_name="run_configs_data",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, config_data_dir]),
                        local_path=f"{sm_processing_output_dir}/{config_data_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                ),
                ProcessingOutput(
                    output_name="run_source_data",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, source_data_dir]),
                        local_path=f"{sm_processing_output_dir}/{source_data_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                )
            ],
            code="step_init.py",
            arguments=[
                "--from-config-path", f"{sm_processing_input_dir}/{config_data_dir}",
                "--to-config-path", f"{sm_processing_output_dir}/{config_data_dir}",
                "--from-data-path", f"{sm_processing_input_dir}/{source_data_dir}",
                "--to-data-path", f"{sm_processing_output_dir}/{source_data_dir}"
            ]
        )    
    )
    
    # ---------- STEP 1: Data Ingestion  --------------- # 
    step_ingest = ProcessingStep(
        name="Ingestion",
        depends_on=[step_init],
        cache_config=cache_config,
        step_args=processor.run(
            inputs=[                
                ProcessingInput(
                    input_name="data_source",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, input_dir]),
                        local_path=f"{sm_processing_input_dir}/{input_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                ),            
                ProcessingInput(
                    input_name="config_schema",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, schema_dir]),
                        local_path=f"{sm_processing_input_dir}/{schema_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                )
            ],
            outputs=[
                ProcessingOutput(
                    output_name="raw_data",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, raw_dir]),
                        local_path=f"{sm_processing_output_dir}/{raw_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                ),
                ProcessingOutput(
                    output_name="extracted_data",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, extract_dir]),
                        local_path=f"{sm_processing_output_dir}/{extract_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                )
            ],
            code="step_ingest.py",
            arguments=[
                "--input-path", f"{sm_processing_input_dir}/{input_dir}", 
                "--raw-path", f"{sm_processing_output_dir}/{raw_dir}",
                "--schema-path", f"{sm_processing_input_dir}/{schema_dir}",
                "--extract-path", f"{sm_processing_output_dir}/{extract_dir}"
            ]
        )    
    )
    
    # ---------- STEP 2: ETL -------------------- #
    step_etl = ProcessingStep(
        name="ETL",
        depends_on=[step_ingest],
        cache_config=cache_config,
        step_args=processor.run(
            inputs=[                
                ProcessingInput(
                    input_name="extracted_data",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, extract_dir]),
                        local_path=f"{sm_processing_input_dir}/{extract_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                ),            
                ProcessingInput(
                    input_name="config_template",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, template_dir]),
                        local_path=f"{sm_processing_input_dir}/{template_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                ),            
                ProcessingInput(
                    input_name="config_schema",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, schema_dir]),
                        local_path=f"{sm_processing_input_dir}/{schema_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                )
            ],
            outputs=[
                ProcessingOutput(
                    output_name="feature_data",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, feature_dir]),
                        local_path=f"{sm_processing_output_dir}/{feature_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                ),
                ProcessingOutput(
                    output_name="dataset_file",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, full_dataset_dir]),
                        local_path=f"{sm_processing_output_dir}/{full_dataset_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                )
            ],
            code="step_etl.py",
            arguments=[
                "--input-path", f"{sm_processing_input_dir}/{extract_dir}",
                "--template-path", f"{sm_processing_input_dir}/{template_dir}",
                "--schema-path", f"{sm_processing_input_dir}/{schema_dir}",
                "--feature-path", f"{sm_processing_output_dir}/{feature_dir}",
                "--output-dataset-file", f"{sm_processing_output_dir}/{full_dataset_dir}/{full_dataset_file}"
            ]
        )    
    )
    
    # ---------- STEP 3: Preprocess ------------- #     
    step_prep = ProcessingStep(
        name="Preprocess",
        depends_on=[step_etl],
        cache_config=cache_config,
        step_args=processor.run(
            inputs=[                
                ProcessingInput(
                    input_name="dataset_file",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, full_dataset_dir]),
                        local_path=f"{sm_processing_input_dir}/{full_dataset_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                )
            ],
            outputs=[
                ProcessingOutput(
                    output_name="split",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, split_dir]),
                        local_path=f"{sm_processing_output_dir}/{split_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                ),
                ProcessingOutput(
                    output_name="format",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, format_dir]),
                        local_path=f"{sm_processing_output_dir}/{format_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                ),
                ProcessingOutput(
                    output_name="token",                 
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, token_dir]),
                        local_path=f"{sm_processing_output_dir}/{token_dir}",
                        s3_upload_mode="EndOfJob"
                    )
                )
            ],
            code="step_prep.py",
            arguments=[
                "--dataset_file", f"{sm_processing_input_dir}/{full_dataset_dir}/{full_dataset_file}",
                "--val-size", str(val_size),
                "--test-size", str(test_size),
                "--seed", str(seed),
                "--model-name", base_model_name,
                "--split-path", f"{sm_processing_output_dir}/{split_dir}",
                "--format-path", f"{sm_processing_output_dir}/{format_dir}",
                "--token-path", f"{sm_processing_output_dir}/{token_dir}",
                "--max-seq-length", str(config["max-seq-length"]),
                "--tracking-run-id", tracking_run_id
            ]
        )    
    )
    
    ################### TRAINING ###################
    training_instance_type    = config["training-instance-type"]
    training_instance_count   = config["training-instance-count"]
    training_spot_instance    = config["training-spot-instance"]
    training_image_uri        = config["training-image-uri"]
    
    # initialise training variables   
    train_dataset_dir       = config["dataset-train-dir"]
    base_model_name         = config["base-model-name"]
    base_model_dir          = config["base-model-dir"]
    model_output_name       = config["model-name"]
    model_output_dir        = config["model-output-dir"]
    model_checkpoint_dir    = config["model-checkpoint-dir"]
    model_config_file       = config["model-config-file"]
    model_config_dir        = config["model-config-dir"]
    local_checkpoint_dir    = "/opt/ml/checkpoints"
    local_model_dir         = "/opt/ml/model"
    
    # ---------- STEP 4: Train ------------- #
    # create checkpoint storage
    s3_client = boto3.client('s3')
    s3_client.put_object(Bucket=bucket_name, Key=model_checkpoint_dir)
    
    model_trainer = ModelTrainer(
        training_image=training_image_uri,
        source_code = SourceCode(
            source_dir=".", 
            entry_script="step_train.py"
        ),
        compute=Compute(
            instance_type=training_instance_type,
            instance_count=training_instance_count,
            enable_managed_spot_training=training_spot_instance,
        ),
        stopping_condition=StoppingCondition(
            max_runtime_in_seconds=86400,       # 24 hour timeout
            # max_wait_time_in_seconds=100000,    # Must be > max_runtime_in_seconds for Spot
        ),
        role=role,
        sagemaker_session=pipeline_session,
        hyperparameters={
            # "base-model-name":f"{base_model_name}", # internal dataset path, use SM_CHANNEL_BASE_MODEL
            "config-file": model_config_file,
            # "dataset-dir":"",                     # internal dataset path, use SM_CHANNEL_DATASET
            # "output-dir":"",                      # internal model output path, SM_MODEL_DIR
            "checkpoint-dir": local_checkpoint_dir,
            "tracking-run-id": tracking_run_id
        },
        input_data_config=[
            InputData(channel_name="model",data_source=f"{bucket_uri}/{base_model_dir}/{base_model_name}"),
            InputData(channel_name="dataset",data_source=Join(on="/", values=[run_uri, run_id, train_dataset_dir])),
            InputData(channel_name="config", data_source=Join(on="/", values=[run_uri, run_id, model_config_dir]))
        ],
        output_data_config=OutputDataConfig(
            s3_output_path=Join(on="/", values=[run_uri, run_id, model_output_dir])
        ),
        checkpoint_config=CheckpointConfig(
            s3_uri=Join(on="/", values=[run_uri, run_id, model_checkpoint_dir]),
            local_path=local_checkpoint_dir # This is the default, but good to be explicit
        )
    )

    step_train = TrainingStep(
        name="Train",
        depends_on=[step_prep],
        cache_config=cache_config,
        step_args=model_trainer.train(),
    )

    # ---------- STEP 5: Evaluate ------------- #
    eval_instance_type  = config["eval-instance-type"]
    eval_instance_count = config["eval-instance-count"]
    eval_image_uri      = config["eval-instance-image"]
    eval_dataset_dir    = config["eval-dataset-dir"]
    metrics_dir         = config["metrics-dir"]
    eval_split          = config.get("eval-split", "test")
    sm_metrics_dir      = "/opt/ml/processing/metrics"

    # eval needs a GPU instance — use a separate processor from the t3 processing one
    eval_processor = FrameworkProcessor(
        image_uri=eval_image_uri,
        instance_type=eval_instance_type,
        instance_count=eval_instance_count,
        sagemaker_session=pipeline_session,
        role=role,
    )

    sm_eval_model_dir = f"{sm_processing_input_dir}/model"

    step_eval = ProcessingStep(
        name="Evaluate",
        depends_on=[step_train],
        step_args=eval_processor.run(
            inputs=[
                ProcessingInput(
                    input_name="eval_model",
                    s3_input=ProcessingS3Input(
                        s3_uri=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                        local_path=sm_eval_model_dir,
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                ),
                ProcessingInput(
                    input_name="eval_dataset",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, eval_dataset_dir]),
                        local_path=f"{sm_processing_input_dir}/{eval_dataset_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                ),
                ProcessingInput(
                    input_name="config",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, model_config_dir]),
                        local_path=f"{sm_processing_input_dir}/{model_config_dir}",
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                ),
            ],
            outputs=[
                ProcessingOutput(
                    output_name="evaluation",
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, metrics_dir]),
                        local_path=sm_metrics_dir,
                        s3_upload_mode="EndOfJob"
                    )
                ),
            ],
            code="step_eval.py",
            arguments=[
                "--model-path",     sm_eval_model_dir,
                "--config-file",    f"{sm_processing_input_dir}/{model_config_dir}/{model_config_file}",
                "--dataset-dir",    f"{sm_processing_input_dir}/{eval_dataset_dir}",
                "--split",          eval_split,
                "--metrics-dir",    sm_metrics_dir,
                "--tracking-run-id", tracking_run_id,
            ],
        ),
    )

    # ---------- STEP 6: Register ------------- #
    step_register = ProcessingStep(
        name="Register",
        depends_on=[step_eval],
        step_args=processor.run(
            inputs=[
                ProcessingInput(
                    input_name="metrics",
                    s3_input=ProcessingS3Input(
                        s3_uri=Join(on="/", values=[run_uri, run_id, metrics_dir]),
                        local_path=sm_metrics_dir,
                        s3_data_type="S3Prefix",
                        s3_input_mode="File",
                        s3_data_distribution_type="FullyReplicated"
                    )
                ),
            ],
            outputs=[
                ProcessingOutput(
                    output_name="registration",
                    s3_output=ProcessingS3Output(
                        s3_uri=Join(on="/", values=[run_uri, run_id, metrics_dir]),
                        local_path=sm_metrics_dir,
                        s3_upload_mode="EndOfJob"
                    )
                ),
            ],
            code="step_register.py",
            arguments=[
                "--model-name",   config["model-name"],
                "--metrics-dir",  sm_metrics_dir,
                "--model-s3-uri", step_train.properties.ModelArtifacts.S3ModelArtifacts,
                "--tracking-run-id", tracking_run_id,
            ],
        ),
    )

    pipeline = Pipeline(
        name=config["pipeline-name"],
        parameters=[run_id],
        steps=[
            step_init,
            step_ingest,
            step_etl,
            step_prep,
            step_train,
            step_eval,
            step_register,
        ],
        sagemaker_session=pipeline_session
    )

    return pipeline
