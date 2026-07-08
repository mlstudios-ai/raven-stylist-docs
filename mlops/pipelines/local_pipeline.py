"""
Local pipeline — runs all pipeline steps sequentially without SageMaker.
Mirrors the step sequence of sm_pipeline.py using local file paths under
outputs/runs/{pipeline_run_name}/ so each run is isolated.
"""
import sys
import subprocess
from pathlib import Path
from sigmoi.utils import get_logger

logger = get_logger("local_pipeline")

PIPELINES_DIR = Path(__file__).parent
PROJECT_ROOT = PIPELINES_DIR.parent
logger.info(f"Runing pipeline from {PROJECT_ROOT}")


class LocalPipeline:
    def __init__(self, name: str, config: dict, pipeline_run_name: str):
        self.name = name
        self.config = config
        self.pipeline_run_name = pipeline_run_name
        self.run_dir = PROJECT_ROOT / "outputs" / "runs" / pipeline_run_name

    def upsert(self, **_):
        logger.info(f"Local pipeline '{self.name}': upsert is a no-op locally")

    def start(self):
        logger.info(f"Starting local pipeline run: {self.pipeline_run_name}")
        self.run_dir.mkdir(parents=True, exist_ok=True)

        c = self.config
        r = self.run_dir

        # Step 0: Init — copy configs and source data into the run directory
        self._run("step_init.py", [
            "--from-config-path", str(PROJECT_ROOT / "configs"),
            "--to-config-path",   str(r / "configs"),
            "--from-data-path",   str(PROJECT_ROOT / c["external-dir"]),
            "--to-data-path",     str(r / c["external-dir"]),
        ])

        # Step 1: Ingest
        self._run("step_ingest.py", [
            # "--input-path",   str(r / c["external-dir"]),
            "--input-path",   str(r / c["external-dir"]),
            "--schema-path",  str(r / c["schema-dir"]),
            "--raw-path",     str(r / c["raw-dir"]),
            "--extract-path", str(r / c["extract-dir"]),
        ])

        # Step 2: ETL
        self._run("step_etl.py", [
            "--input-path",          str(r / c["extract-dir"]),
            "--template-path",       str(r / c["template-dir"]),
            "--schema-path",         str(r / c["schema-dir"]),
            "--feature-path",        str(r / c["feature-dir"]),
            "--output-dataset-file", str(r / c["dataset-file-path"]),
        ])

        # Step 3: Prep
        self._run("step_prep.py", [
            "--dataset_file",   str(r / c["dataset-file-path"]),
            "--val-size",       str(c["split-val-size"]),
            "--test-size",      str(c["split-test-size"]),
            "--seed",           str(c["split-seed"]),
            "--model-name",     c["base-model-name"],
            "--split-path",     str(r / c["dataset-split-dir"]),
            "--format-path",    str(r / c["dataset-formatted-dir"]),
            "--token-path",     str(r / c["dataset-tokenized-dir"]),
            "--max-seq-length", str(c["max-seq-length"]),
        ])

        # Step 4: Train
        self._run("step_train.py", [
            "--base-model-name", c["base-model-name"],
            "--config-file",     c["model-config-file"],
            "--dataset-dir",     str(r / c["dataset-train-dir"]),
            "--output-dir",      str(r / c["model-output-dir"]),
            "--checkpoint-dir",  str(r / c["model-checkpoint-dir"]),
            "--metrics-dir",     str(r / c["metrics-dir"]),
        ])

        # Step 5: Eval
        self._run("step_eval.py", [
            "--model-path",         str(r / c["model-output-dir"]),
            "--dataset-dir",        str(r / c["eval-dataset-dir"]),
            "--metrics-dir",        str(r / c["metrics-dir"]),
            "--judge-metrics-file", c["judge-metrics-file"],
            "--judge-provider",     c["judge-provider"],
            "--judge-model-id",     c["judge-model-id"],
            "--judge-max-tokens",   str(c["judge-max-tokens"]),
        ])

        # Step 6: Register
        self._run("step_register.py", [
            "--model-path",  str(r / c["model-output-dir"]),
            "--model-name",  c["model-name"],
            "--metrics-dir", str(r / c["metrics-dir"]),
        ])

        logger.info(f"Local pipeline run complete: {self.pipeline_run_name}")
        logger.info(f"Outputs at: {self.run_dir}")

    def _run(self, script: str, args: list[str] = []):
        cmd = [sys.executable, str(PIPELINES_DIR / script)] + args
        logger.info(f"--- {script} ---")
        subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def build_pipeline(
    name: str,
    config: dict,
    pipeline_run_name: str,
) -> LocalPipeline:
    return LocalPipeline(name, config, pipeline_run_name)
