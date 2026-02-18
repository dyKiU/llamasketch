#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Vast.ai ComfyUI Instance Setup Script
# Downloads FLUX Klein 4B models and verifies the environment.
# Idempotent: safe to run multiple times.
# =============================================================================

COMFYUI_DIR="/workspace/ComfyUI"
MODELS_DIR="${COMFYUI_DIR}/models"

# Model definitions: name | destination dir | URL | minimum size in bytes
MODELS=(
  "flux-2-klein-4b-fp8.safetensors|${MODELS_DIR}/diffusion_models|https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors|3000000000"
  "qwen_3_4b.safetensors|${MODELS_DIR}/text_encoders|https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors|7000000000"
  "flux2-vae.safetensors|${MODELS_DIR}/vae|https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors|300000000"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---- Step 1: Verify ComfyUI directory exists ----
info "Step 1: Checking ComfyUI installation..."
if [ ! -d "${COMFYUI_DIR}" ]; then
    error "ComfyUI directory not found at ${COMFYUI_DIR}"
    error "Make sure you're using the Vast.ai ComfyUI template."
    exit 1
fi
info "ComfyUI found at ${COMFYUI_DIR}"

# ---- Step 2: Install pip dependencies ----
info "Step 2: Installing pip dependencies..."
pip install --quiet huggingface_hub Pillow requests
info "Dependencies installed."

# ---- Step 3: Download models ----
info "Step 3: Downloading models (~12.5 GB total)..."

for model_spec in "${MODELS[@]}"; do
    IFS='|' read -r filename dest_dir url min_size <<< "${model_spec}"
    filepath="${dest_dir}/${filename}"

    # Create destination directory if needed
    mkdir -p "${dest_dir}"

    # Check if file already exists with sufficient size
    if [ -f "${filepath}" ]; then
        actual_size=$(stat -c%s "${filepath}" 2>/dev/null || stat -f%z "${filepath}" 2>/dev/null || echo 0)
        if [ "${actual_size}" -ge "${min_size}" ]; then
            info "  ${filename} already exists ($(numfmt --to=iec ${actual_size} 2>/dev/null || echo "${actual_size} bytes")), skipping."
            continue
        else
            warn "  ${filename} exists but is too small (${actual_size} < ${min_size}), re-downloading..."
        fi
    fi

    info "  Downloading ${filename}..."
    wget -c --progress=bar:force:noscroll -O "${filepath}" "${url}"
    info "  ${filename} downloaded."
done

# ---- Step 4: Verify all model files ----
info "Step 4: Verifying model files..."
all_ok=true
for model_spec in "${MODELS[@]}"; do
    IFS='|' read -r filename dest_dir url min_size <<< "${model_spec}"
    filepath="${dest_dir}/${filename}"

    if [ ! -f "${filepath}" ]; then
        error "  MISSING: ${filepath}"
        all_ok=false
        continue
    fi

    actual_size=$(stat -c%s "${filepath}" 2>/dev/null || stat -f%z "${filepath}" 2>/dev/null || echo 0)
    if [ "${actual_size}" -lt "${min_size}" ]; then
        error "  TOO SMALL: ${filepath} (${actual_size} bytes, expected >= ${min_size})"
        all_ok=false
    else
        size_human=$(numfmt --to=iec ${actual_size} 2>/dev/null || echo "${actual_size} bytes")
        info "  OK: ${filename} (${size_human})"
    fi
done

if [ "${all_ok}" = false ]; then
    error "Some model files are missing or incomplete. Re-run this script."
    exit 1
fi
info "All model files verified."

# ---- Step 5: Check if ComfyUI is running ----
info "Step 5: Checking if ComfyUI is running on port 8188..."
if curl -s --max-time 5 http://127.0.0.1:8188/ > /dev/null 2>&1; then
    info "ComfyUI is running on port 8188."
else
    warn "ComfyUI is NOT responding on port 8188."
    warn "It may need to be started or restarted to load the new models."
    warn "Check with: curl http://127.0.0.1:8188/"
fi

# ---- Step 6: Copy test files if present alongside this script ----
info "Step 6: Checking for test files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for file in "workflow_template.json" "test_inference.py"; do
    # Check next to this script
    if [ -f "${SCRIPT_DIR}/${file}" ]; then
        cp "${SCRIPT_DIR}/${file}" "/workspace/${file}"
        info "  Copied ${file} to /workspace/"
    # Check in parent directory (for workflow_template.json at project root)
    elif [ -f "${SCRIPT_DIR}/../${file}" ]; then
        cp "${SCRIPT_DIR}/../${file}" "/workspace/${file}"
        info "  Copied ${file} to /workspace/"
    elif [ -f "/workspace/${file}" ]; then
        info "  ${file} already in /workspace/"
    else
        warn "  ${file} not found. Copy it manually to /workspace/"
    fi
done

# ---- Summary ----
echo ""
echo "============================================"
info "Setup complete!"
echo "============================================"
echo ""
echo "Models installed:"
echo "  - diffusion_models/flux-2-klein-4b-fp8.safetensors"
echo "  - text_encoders/qwen_3_4b.safetensors"
echo "  - vae/flux2-vae.safetensors"
echo ""
echo "Next steps:"
echo "  1. Ensure ComfyUI is running (check port 8188)"
echo "  2. If models were just downloaded, restart ComfyUI"
echo "  3. Run tests: cd /workspace && python3 test_inference.py"
echo ""
