FROM public.ecr.aws/deep-learning-containers/pytorch-training:2.7.1-gpu-py312-cu128-ubuntu22.04-sagemaker-v1.28

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libcurl4-openssl-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

RUN pip install ninja packaging setuptools wheel uv

# Required so CUDA extension builds link against the same runtime as the
# DLC's PyTorch (cu128). Covers V100, A100, A10G, H100 SageMaker families.
ENV CUDA_HOME=/usr/local/cuda
ENV TORCH_CUDA_ARCH_LIST="7.0;8.0;8.6;9.0"
ENV MAX_JOBS=4

# Install requirements first (includes unsloth with all its deps so packages
# like datasets, tokenizers, etc. are present).
COPY docker/requirements.txt /tmp/requirements.txt
RUN uv pip install --system --no-cache -r /tmp/requirements.txt

# Force-rebuild mamba/causal from source last so they override any binary
# wheels that unsloth pulled in that are incompatible with cu128.
# RUN CAUSAL_CONV1D_FORCE_BUILD=TRUE pip install "causal-conv1d>=1.4.0" --no-build-isolation
# RUN MAMBA_FORCE_BUILD=TRUE pip install mamba-ssm --no-build-isolation

COPY src/ /opt/sigmoi/src/

# Make sigmoi importable, and cover both SageMaker conventions:
#   training   → /opt/ml/code/src
#   processing → /opt/ml/processing/input/code/src
ENV PYTHONPATH="/opt/sigmoi/src:/opt/ml/code/src:/opt/ml/processing/input/code/src:${PYTHONPATH:-}"

WORKDIR /opt/ml
