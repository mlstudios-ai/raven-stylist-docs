#!/usr/bin/env bash
# Usage:
#   ./docker/image.sh build            — build the image locally
#   ./docker/image.sh push [tag]       — build + push to ECR (default tag: latest)
#   ./docker/image.sh remove [tag]     — delete an image from ECR (default tag: latest)

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
REPO_NAME="${PROJECT_NAME}-base-image"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
FULL_REPO="${ECR_REGISTRY}/${REPO_NAME}"

TAG="${2:-latest}"

# ── Helpers ───────────────────────────────────────────────────────────────────
ecr_login() {
  echo "→ Logging in to ECR: $1"
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "$1"
}

# ── Commands ──────────────────────────────────────────────────────────────────
cmd_build() {
  echo "→ Building image: ${FULL_REPO}:${TAG}"
  docker build \
    --platform linux/amd64 \
    -f docker/Dockerfile \
    -t "${FULL_REPO}:${TAG}" \
    docker/
}

cmd_push() {
  cmd_build
  ecr_login "${ECR_REGISTRY}"
  echo "→ Pushing image: ${FULL_REPO}:${TAG}"
  docker push "${FULL_REPO}:${TAG}"
  echo "✓ Pushed: ${FULL_REPO}:${TAG}"
}

cmd_remove() {
  echo "→ Deleting image from ECR: ${REPO_NAME}:${TAG}"
  aws ecr batch-delete-image \
    --region "${AWS_REGION}" \
    --repository-name "${REPO_NAME}" \
    --image-ids imageTag="${TAG}"
  echo "✓ Deleted: ${REPO_NAME}:${TAG}"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "${1:-}" in
  build)  cmd_build  ;;
  push)   cmd_push   ;;
  remove) cmd_remove ;;
  *)
    echo "Usage: $0 {build|push|remove} [tag]"
    exit 1
    ;;
esac

