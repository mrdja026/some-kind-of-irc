#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
AUTO_INSTALL_CUDA_TOOLKIT=${AUTO_INSTALL_CUDA_TOOLKIT:-false}

if ! command -v nvcc >/dev/null 2>&1; then
  if [ "$AUTO_INSTALL_CUDA_TOOLKIT" = "true" ]; then
    echo "nvcc not found. Installing CUDA toolkit via apt..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
  else
    echo "nvcc not found. Set AUTO_INSTALL_CUDA_TOOLKIT=true to install via apt."
  fi
fi

if [ -d "/usr/local/cuda/bin" ] && ! echo "$PATH" | grep -q "/usr/local/cuda/bin"; then
  export PATH="/usr/local/cuda/bin:$PATH"
fi

if [ ! -x "$VENV_DIR/bin/python" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
  rm -rf "$VENV_DIR"
  if ! python3 -m venv "$VENV_DIR"; then
    echo "Failed to create venv. Install python3-venv and retry."
    echo "Example: sudo apt-get update && sudo apt-get install -y python3-venv"
    exit 1
  fi
fi

VENV_PY="$VENV_DIR/bin/python"

if [ ! -x "$VENV_PY" ]; then
  echo "Python not found in venv. Remove .venv and retry."
  exit 1
fi

"$VENV_PY" -m pip install -U pip
"$VENV_PY" -m pip install -r "$PROJECT_DIR/requirements-app.txt"

export SERVICE_HOST="0.0.0.0"
export SERVICE_PORT="8100"
export VLLM_PORT="8000"
export VLLM_API_URL="http://localhost:${VLLM_PORT}/v1/completions"
export VLLM_MODEL_ID="${VLLM_MODEL_ID:-$PROJECT_DIR/models/Arch-Function-3B-Q6_K.gguf}"
export VLLM_SERVED_MODEL_NAME="${VLLM_SERVED_MODEL_NAME:-katanemo/Arch-Function-3B}"
export VLLM_TOKENIZER="${VLLM_TOKENIZER:-katanemo/Arch-Function-3B}"
export VLLM_QUANTIZATION="${VLLM_QUANTIZATION:-gguf}"
export VLLM_LOAD_FORMAT="${VLLM_LOAD_FORMAT:-gguf}"
export VLLM_DTYPE="${VLLM_DTYPE:-auto}"
export VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-2048}"
export VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.55}"
export VLLM_ENFORCE_EAGER="${VLLM_ENFORCE_EAGER:-true}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

if [[ "$VLLM_MODEL_ID" == *.gguf ]] && [[ ! -f "$VLLM_MODEL_ID" ]]; then
  echo "GGUF model file not found: $VLLM_MODEL_ID"
  echo "Set VLLM_MODEL_ID to a valid Q6 GGUF file path and retry."
  exit 1
fi

exec "$VENV_PY" "$PROJECT_DIR/quant_arch_function_3b.py"
