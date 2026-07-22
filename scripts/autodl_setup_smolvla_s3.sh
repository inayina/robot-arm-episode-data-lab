#!/usr/bin/env bash
# Repeatable AutoDL env setup for SmolVLA S3. Does not use system Python.
# Does not download full model weights unless SMOLVLA_S3_DOWNLOAD_BASE=1.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${S3_CONDA_ENV:-smolvla_s3}"
LOCK="$ROOT/configs/smolvla_s3/environment.lock.txt"
HF_HOME="${HF_HOME:-$HOME/autodl-tmp/hf_cache}"
PIP_CACHE_DIR="${PIP_CACHE_DIR:-$HOME/autodl-tmp/pip_cache}"

echo "[autodl-setup] ROOT=$ROOT"
echo "[autodl-setup] ENV_NAME=$ENV_NAME"
echo "[autodl-setup] HF_HOME=$HF_HOME"

mkdir -p "$HF_HOME" "$PIP_CACHE_DIR" "$HOME/autodl-tmp/smolvla_s3"

# Disk precheck (GB)
python3 - <<'PY'
import shutil
from pathlib import Path
home = Path.home()
usage = shutil.disk_usage(str(home))
free_gb = usage.free / (1024**3)
print(f"[autodl-setup] disk_free_gb={free_gb:.1f}")
# Need ~25GB: base~2GB + VLM~2GB + env~8GB + data~2GB + runs~5GB + margin
if free_gb < 25:
    raise SystemExit(f"disk free {free_gb:.1f}GB < 25GB minimum for S3")
PY

echo "[autodl-setup] GPU:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv || {
  echo "[autodl-setup] FATAL: nvidia-smi failed" >&2
  exit 2
}

# Prefer conda if available; else venv under autodl-tmp
if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    conda create -y -n "$ENV_NAME" python=3.11
  fi
  conda activate "$ENV_NAME"
else
  VENV="$HOME/autodl-tmp/venvs/$ENV_NAME"
  if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

python - <<'PY'
import sys
print("python", sys.version)
assert not sys.prefix.startswith("/usr") or "venv" in sys.prefix or ".conda" in sys.prefix or "miniconda" in sys.prefix or "miniforge" in sys.prefix or "autodl-tmp" in sys.prefix, sys.prefix
PY

python -m pip install -U pip setuptools wheel
# Torch CUDA wheel — preflight-bound; default cu124. Override with S3_TORCH_INDEX.
TORCH_INDEX="${S3_TORCH_INDEX:-https://download.pytorch.org/whl/cu124}"
python -m pip install torch torchvision --index-url "$TORCH_INDEX"
python -m pip install -r "$LOCK"

python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
    props = torch.cuda.get_device_properties(0)
    print("vram_total_gb", round(props.total_memory / (1024**3), 2))
    if props.total_memory < 15 * (1024**3):
        raise SystemExit("GPU VRAM < 15GB — S3 LoRA No-Go on this instance")
PY

export HF_HOME
export HUGGINGFACE_HUB_CACHE="$HF_HOME/hub"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"

if [[ "${SMOLVLA_S3_DOWNLOAD_BASE:-0}" == "1" ]]; then
  echo "[autodl-setup] downloading lerobot/smolvla_base (explicit flag)"
  python - <<'PY'
from huggingface_hub import snapshot_download
import os
dest = os.path.expanduser("~/autodl-tmp/smolvla_s3/smolvla_base")
snapshot_download(repo_id="lerobot/smolvla_base", local_dir=dest)
print("downloaded", dest)
PY
else
  echo "[autodl-setup] skip base download (set SMOLVLA_S3_DOWNLOAD_BASE=1 when ready)"
fi

python - <<PY
import json, os, subprocess, torch
from pathlib import Path
out = Path(os.path.expanduser("~/autodl-tmp/smolvla_s3/env_versions.json"))
info = {
  "torch": torch.__version__,
  "cuda_available": torch.cuda.is_available(),
  "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
  "vram_total_mib": int(torch.cuda.get_device_properties(0).total_memory/1024/1024) if torch.cuda.is_available() else None,
  "hf_home": os.environ.get("HF_HOME"),
}
try:
  import peft, transformers, lerobot
  info["peft"] = peft.__version__
  info["transformers"] = transformers.__version__
  info["lerobot"] = getattr(lerobot, "__version__", "unknown")
except Exception as e:
  info["import_error"] = str(e)
out.write_text(json.dumps(info, indent=2) + "\n")
print("wrote", out)
PY

echo "[autodl-setup] done. Next: checkout fixed commit, mount release sources, run preflight."
echo "[autodl-setup] NEVER put HF tokens into the git repo; use 'huggingface-cli login' or env on the instance only."
