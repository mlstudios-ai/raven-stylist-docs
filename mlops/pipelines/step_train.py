"""
SageMaker Training step — AI stylist model.

Wraps: sigmoi.training.train
Responsibility: resolve SageMaker env vars (data channels, model dir, HPCs),
call core trainer, save model artifact to SIGMOI_MODEL_DIR.
"""
import argparse
import os
import yaml
import json
import mlflow
from pathlib import Path
from sigmoi.utils import get_logger
from sigmoi.train import UnslothTrainer

logger = get_logger("pipelines.step_train")

config_file = Path("pipeline-config.yaml")
if not config_file.exists():
    config_file = Path("pipelines/pipeline-config.yaml")
    
if not config_file.exists():
    raise RuntimeError(f"pipeline-config.yamlnot found in expected locations.")
    
with config_file.open("r") as f:
    config = yaml.safe_load(f)
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model-name", type=str, default=os.environ.get("SM_CHANNEL_MODEL", config["base-model-name"]))
    parser.add_argument("--config-file", type=str, default=config["model-config-file"])
    parser.add_argument("--dataset-dir", type=str, default=os.environ.get("SM_CHANNEL_DATASET", config["dataset-train-dir"]))
    parser.add_argument("--output-dir", type=str, default=os.environ.get("SM_MODEL_DIR", config["model-output-dir"]))
    parser.add_argument("--checkpoint-dir", type=str, default=os.environ.get("SM_CHECKPOINT_LOCAL_PATH", config["model-checkpoint-dir"]))
    parser.add_argument("--metrics-dir",    type=str, default=os.environ.get("SM_OUTPUT_DATA_DIR", config["metrics-dir"]))
    parser.add_argument("--eval-metrics-file",      type=str, default=config["eval-metrics-file"])
    parser.add_argument("--tracking-run-id", type=str, default=None)

    os.environ.setdefault("MLFLOW_TRACKING_URI", config["mlflow-tracking-uri"])
    os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", config["mlflow-experiment-name"])
    os.environ.setdefault("AWS_REGION", config["region"])

    args = parser.parse_args()
    if args.tracking_run_id:
        os.environ.setdefault("MLFLOW_RUN_ID", args.tracking_run_id)
    
    base_model_name = args.base_model_name

    if not os.environ.get("SM_CHANNEL_MODEL"):
        # model is not set by remote trainign job
        local_model_path = Path(config["base-model-dir"]) / base_model_name
        if local_model_path.exists() : # if local copy exist, use it
            base_model_name = str(local_model_path)
            
    logger.info(f"Base model: {base_model_name}")

    config_file = args.config_file
    dataset_dir = Path(args.dataset_dir)
    output_dir = Path(args.output_dir)
    checkpoint_dir = Path(args.checkpoint_dir)
    
    # if SM_CHANNEL_CONFIG is set when run remotely, if not set local config dir
    model_config_dir = os.environ.get("SM_CHANNEL_CONFIG")
    model_config_dir = model_config_dir if model_config_dir else config["model-config-dir"]
    model_config_dir = Path(model_config_dir)

    # get model training condfig file
    hyps_path = model_config_dir / config_file    
    
    with open(hyps_path, "r") as f:
        hyps = yaml.safe_load(f)
        # resolve deepspeed config path
        deepspeed_config_path = hyps["trainer"]["deepspeed_config_path"]
        
        if deepspeed_config_path:
            deepspeed_config_path = model_config_dir / deepspeed_config_path
            
        hyps["trainer"]["deepspeed_config_path"] = str(deepspeed_config_path)
        
        logger.info(f"Loaded hyperparameters from {hyps_path}")

    trainer = UnslothTrainer(base_model_name, output_dir, checkpoint_dir)
    # trainer.load_dataset_from(dataset_dir, data_format="arrow") # tokenized dataset
    trainer.load_dataset_from(dataset_dir, data_format="json") # text dataset, unsloth trainer will tokenize on the fly
    trainer.load_hyps(hyps)
    trainer.add_tracker(name="mlflow")
    metric_summary = trainer.train()

    metrics_dir = Path(args.metrics_dir)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_file_path = metrics_dir / args.eval_metrics_file

    with open(metrics_file_path, "w") as f:
        json.dump(metric_summary, f, indent=2)

    run_id = os.environ.get("MLFLOW_RUN_ID")
    with mlflow.start_run(run_id=run_id):
        for key in ("eval_loss", "perplexity", "epoch", "global_step"):
            value = metric_summary.get(key)
            if value is not None:
                mlflow.log_metric(key, value)

    logger.info(f"Training complete.")

if __name__ == "__main__":
    main()
