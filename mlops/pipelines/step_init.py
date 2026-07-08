"""
SageMaker Processing step — ETL

Wraps: sigmoi.features.engineer
Responsibility: resolve S3 paths from SageMaker env, call core feature
engineer, write outputs.
"""
import argparse
import shutil
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-config-path", type=str, required=True)
    parser.add_argument("--to-config-path", type=str, required=True)
    parser.add_argument("--from-data-path", type=str, required=True)
    parser.add_argument("--to-data-path", type=str, required=True)
    
    args = parser.parse_args()
    
    shutil.copytree(Path(args.from_config_path), Path(args.to_config_path), dirs_exist_ok=True)
    shutil.copytree(Path(args.from_data_path), Path(args.to_data_path), dirs_exist_ok=True)

if __name__ == "__main__":
    main()
