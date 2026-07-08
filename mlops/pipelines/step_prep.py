"""
SageMaker Processing step — preprocessing.

Wraps: sigmoi.data.preprocessing
Responsibility: resolve S3 paths from SageMaker env, call core preprocessor, write outputs.
"""
import argparse
import json
import os
from collections import Counter
import yaml
import mlflow
from pathlib import Path
from transformers import AutoTokenizer

from sigmoi.data.preprocess import split, format, tokenize
from sigmoi.utils import get_logger

logger = get_logger("pipelines.step_prep")

config_file = Path("pipeline-config.yaml")
if not config_file.exists():
    config_file = Path("pipelines/pipeline-config.yaml")
    
if not config_file.exists():
    raise RuntimeError(f"pipeline-config.yamlnot found in expected locations.")
    
with config_file.open("r") as f:
    config = yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_file", type=str, default=config["dataset-file-path"]) 
    parser.add_argument("--val-size", type=float, default=config["split-val-size"])
    parser.add_argument("--test-size", type=float, default=config["split-test-size"])
    parser.add_argument("--seed", type=int, default=config["split-seed"])    
    parser.add_argument("--model-name", type=str, default=config["base-model-name"]) 
    parser.add_argument("--split-path", type=str, default=config["dataset-split-dir"]) 
    parser.add_argument("--format-path", type=str, default=config["dataset-formatted-dir"])
    parser.add_argument("--token-path", type=str, default=config["dataset-tokenized-dir"])
    parser.add_argument("--max-seq-length", type=int, default=config["max-seq-length"])
    parser.add_argument("--tracking-run-id", type=str, default=None)
    args = parser.parse_args()

    dataset_file_path=args.dataset_file
    val_size=args.val_size
    test_size=args.test_size
    seed=args.seed
    model_name=args.model_name
    split_path = Path(args.split_path)
    format_path = Path(args.format_path)
    token_path = Path(args.token_path)
    max_seq_length = args.max_seq_length

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    dataset   = split(dataset_file_path, split_path, valid_size=val_size, test_size=test_size, seed=seed)
    format(split_path, format_path, tokenizer=tokenizer)
    tokenized = tokenize(format_path, output_dir=token_path, tokenizer=tokenizer, max_length=max_seq_length)

    tracking_run_id = args.tracking_run_id or os.environ.get("MLFLOW_RUN_ID")
    if tracking_run_id:
        mlflow.set_tracking_uri(config["mlflow-tracking-uri"])
        with mlflow.start_run(run_id=tracking_run_id):
            mlflow.log_params({
                "prep.val_size":       val_size,
                "prep.test_size":      test_size,
                "prep.seed":           seed,
                "prep.max_seq_length": max_seq_length,
                "prep.model_name":     model_name,
            })

            # split counts
            mlflow.log_metrics({
                f"dataset.{split_name}_count": len(ds)
                for split_name, ds in dataset.items()
            })

            # categorical distributions per split
            for field in ("task", "context_level", "gender_identity"):
                if field not in dataset["train"].column_names:
                    continue
                for split_name, ds in dataset.items():
                    for value, count in Counter(ds[field]).items():
                        if value is None:
                            continue
                        mlflow.log_metric(f"dataset.{split_name}_{field}_{value}_count", count)

            # token length stats per split
            for split_name, ds in tokenized.items():
                lengths = sorted(len(ids) for ids in ds["input_ids"])
                if not lengths:
                    continue
                p95 = lengths[int(len(lengths) * 0.95)]
                truncated = sum(1 for l in lengths if l == max_seq_length)
                mlflow.log_metrics({
                    f"dataset.{split_name}_token_mean":      sum(lengths) / len(lengths),
                    f"dataset.{split_name}_token_max":       lengths[-1],
                    f"dataset.{split_name}_token_p95":       p95,
                    f"dataset.{split_name}_token_truncated": truncated,
                })

if __name__ == "__main__":
    main()
