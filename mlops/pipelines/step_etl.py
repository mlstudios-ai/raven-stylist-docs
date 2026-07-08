"""
SageMaker Processing step — ETL

Wraps: sigmoi.features.engineer
Responsibility: resolve S3 paths from SageMaker env, call core feature
engineer, write outputs.
"""
import argparse
import json
import os
from pathlib import Path
import yaml

from sigmoi.data.transform import engineer_features, transform
from sigmoi.utils import get_logger

logger = get_logger("pipelines.step_etl")

config_file = Path("pipeline-config.yaml")
if not config_file.exists():
    config_file = Path("pipelines/pipeline-config.yaml")
    
if not config_file.exists():
    raise RuntimeError(f"pipeline-config.yamlnot found in expected locations.")
    
with config_file.open("r") as f:
    config = yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", type=str, default=config["extract-dir"])
    parser.add_argument("--template-path", type=str, default=config["template-dir"])
    parser.add_argument("--schema-path", type=str, default=config["schema-dir"])
    parser.add_argument("--feature-path", type=str, default=config["feature-dir"])
    parser.add_argument("--output-dataset-file", type=str, default=config["dataset-file-path"])
    
    args = parser.parse_args()
    
    extract_path = Path(args.input_path)
    feature_path = Path(args.feature_path)
    schema_path = Path(args.schema_path)
    template_path = Path(args.template_path)
    output_file = Path(args.output_dataset_file)

    engineer_features(extract_path, feature_path, schema_path)
    transform(feature_path, output_file, template_path, schema_dir=schema_path)

if __name__ == "__main__":
    main()
