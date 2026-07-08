"""
Evaluation step — runs loss/perplexity/ROUGE/JSON-validity metrics on the
trained model and optionally runs the LLM judge.

Reads defaults from pipeline-config.yaml; all values can be overridden via CLI.
MLflow configuration is picked up from env vars (MLFLOW_TRACKING_URI etc.).
"""
import argparse
import os
import tarfile
from pathlib import Path
import json

import mlflow
import yaml

from sigmoi.model import SigmoiJudge
from sigmoi.model import UnslothEval
from sigmoi.utils import get_logger

logger = get_logger("pipelines.step_eval")


def _resolve_model_path(model_path: str) -> str:
    """Extract model.tar.gz if present (SageMaker training output is tarred)."""
    p = Path(model_path)
    tarball = p / "model.tar.gz"
    if tarball.exists():
        extract_dir = p / "extracted"
        extract_dir.mkdir(exist_ok=True)
        logger.info(f"Extracting {tarball} → {extract_dir}")
        with tarfile.open(tarball) as tf:
            tf.extractall(extract_dir)
        return str(extract_dir)
    return model_path


def _load_config() -> dict:
    for candidate in ("pipeline-config.yaml", "pipelines/pipeline-config.yaml"):
        p = Path(candidate)
        if p.exists():
            with p.open() as f:
                return yaml.safe_load(f)
    raise RuntimeError("pipeline-config.yaml not found")


def main() -> None:
    config = _load_config()

    parser = argparse.ArgumentParser(description="Evaluate trained model")
    parser.add_argument("--model-path",     type=str, default=os.environ.get("SM_CHANNEL_MODEL", config["model-output-dir"]))
    parser.add_argument("--config-file", type=str, default=config["model-config-file"])
    parser.add_argument("--dataset-dir",    type=str, default=os.environ.get("SM_CHANNEL_DATASET", config["eval-dataset-dir"]))
    parser.add_argument("--split",          type=str, default=config.get("eval-split", "test"))
    parser.add_argument("--max-new-tokens", type=int, default=config.get("eval-max-new-tokens", 1024))
    parser.add_argument("--judge-provider", type=str, default=config["judge-provider"])
    parser.add_argument("--judge-model-id", type=str, default=config["judge-model-id"])
    parser.add_argument("--judge-max-tokens", type=int, default=int(config["judge-max-tokens"]))
    parser.add_argument("--metrics-dir",    type=str, default=config["metrics-dir"])
    parser.add_argument("--judge-metrics-file", type=str, default=config["judge-metrics-file"])
    # mlflow
    parser.add_argument("--tracking-run-id", type=str, default=None)
    args = parser.parse_args()

    os.environ.setdefault("MLFLOW_TRACKING_URI",   config["mlflow-tracking-uri"])
    os.environ.setdefault("MLFLOW_EXPERIMENT_NAME", config["mlflow-experiment-name"])
    if args.tracking_run_id:
        os.environ.setdefault("MLFLOW_RUN_ID", args.tracking_run_id)

    model_path  = args.model_path 
    dataset_dir = args.dataset_dir
    
    model_config_dir = os.environ.get("SM_CHANNEL_CONFIG")
    model_config_dir = model_config_dir if model_config_dir else config["model-config-dir"]
    model_config_dir = Path(model_config_dir)
    # get model training condfig file
    hyps_path = model_config_dir / args.config_file    

    metrics_dir = Path(args.metrics_dir)

    if not model_path:
        raise ValueError("Model path required — pass --model-path or set SM_CHANNEL_MODEL")
    if not dataset_dir:
        raise ValueError("Dataset path required — pass --dataset-dir or set SM_CHANNEL_DATASET")

    if os.environ.get("SM_CHANNEL_MODEL"): # remote run, unzip tar file
        model_path = _resolve_model_path(model_path)
        
    logger.info(f"Evaluating model at {model_path} with dataset at {dataset_dir} on split={args.split}")

    # LLMJudge - compares against ground truth (prompt, expected, prediction)
    model_eval = UnslothEval(model_name=model_path, dataset_dir=dataset_dir, hyps_path=hyps_path)

    judge = SigmoiJudge(
        provider=args.judge_provider,
        model_id=args.judge_model_id,  # or None for default
        max_tokens=args.judge_max_tokens
    )

    prompts, targets, predictions, base_preds = model_eval.predict(
        split = args.split,
        task = "SIGMOI_STYLE",
        prompt_output_file = metrics_dir / Path(config["eval-style-prompts-file"]).name,
        target_output_file = metrics_dir / Path(config["eval-style-targets-file"]).name,
        prediction_output_file = metrics_dir / Path(config["eval-style-predictions-file"]).name,
        prediction_base_output_file = metrics_dir / Path(config["eval-style-predictions-base-file"]).name,
        max_new_tokens=args.max_new_tokens
    )

    metrics = judge.judge_from(
        task = "SIGMOI_STYLE",
        prompt_file=metrics_dir / Path(config["eval-style-prompts-file"]).name,
        target_file=metrics_dir / Path(config["eval-style-targets-file"]).name,
        prediction_file=metrics_dir / Path(config["eval-style-predictions-file"]).name,
        base_file=metrics_dir / Path(config["eval-style-predictions-base-file"]).name,
        output_file=metrics_dir / args.judge_metrics_file)

    mean_scores = metrics.get("mean_scores", {})
    pred_scores = mean_scores.get("prediction", {})
    base_scores = mean_scores.get("base_prediction", {})

    run_id = os.environ.get("MLFLOW_RUN_ID")
    with mlflow.start_run(run_id=run_id):
        for criterion, score in pred_scores.items():
            mlflow.log_metric(f"judge_{criterion}", score)
        for criterion, score in base_scores.items():
            mlflow.log_metric(f"base_judge_{criterion}", score)
        if pred_scores:
            mlflow.log_metric("judge_mean", sum(pred_scores.values()) / len(pred_scores))

if __name__ == "__main__":
    main()
