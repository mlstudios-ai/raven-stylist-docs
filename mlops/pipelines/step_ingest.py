"""
SageMaker Processing step — data ingestion.

Wraps: sigmoi.data.loader
Responsibility: resolve S3 paths from SageMaker env, call core loader, write outputs.
"""
import argparse
import os
import yaml
from pathlib import Path
from sigmoi.utils import get_logger
from sigmoi.data.transform import select_features
from sigmoi.data.loader import load_raw_data

logger = get_logger("pipelines.step_ingest")

config_file = Path("pipeline-config.yaml")
if not config_file.exists():
    config_file = Path("pipelines/pipeline-config.yaml")
    
if not config_file.exists():
    raise RuntimeError(f"pipeline-config.yamlnot found in expected locations.")
    
with config_file.open("r") as f:
    config = yaml.safe_load(f)
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", type=str, default=config["external-dir"])
    parser.add_argument("--schema-path", type=str, default=config["schema-dir"])
    parser.add_argument("--raw-path", type=str, default=config["raw-dir"])
    parser.add_argument("--extract-path", type=str, default=config["extract-dir"])
    
    args = parser.parse_args()
    
    input_path = Path(args.input_path)
    schema_path = Path(args.schema_path)
    raw_path = Path(args.raw_path)  
    extract_path = Path(args.extract_path)

    load_raw_data(input_path, raw_path)        
    select_features(raw_path, extract_path, schema_path)
    logger.info(f"Ingested data from {input_path} → {raw_path} → {extract_path}")
        
if __name__ == "__main__":
    main()
