#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ComfyUI Cleanup Script
# Removes stale input/output images older than MAX_AGE_MINUTES.
# Intended to run via cron on the Vast.ai GPU instance.
#
# Usage:
#   bash /workspace/cleanup_comfyui.sh          # delete files older than 60 min
#   MAX_AGE_MINUTES=30 bash cleanup_comfyui.sh  # custom age threshold
#
# Cron setup (run every 30 minutes):
#   echo "*/30 * * * * /workspace/cleanup_comfyui.sh >> /var/log/comfyui-cleanup.log 2>&1" \
#     | crontab -
# =============================================================================

COMFYUI_DIR="${COMFYUI_DIR:-/workspace/ComfyUI}"
MAX_AGE_MINUTES="${MAX_AGE_MINUTES:-60}"

INPUT_DIR="${COMFYUI_DIR}/input"
OUTPUT_DIR="${COMFYUI_DIR}/output"

deleted=0

for dir in "${INPUT_DIR}" "${OUTPUT_DIR}"; do
    if [ ! -d "${dir}" ]; then
        continue
    fi
    while IFS= read -r -d '' file; do
        rm -f "${file}"
        deleted=$((deleted + 1))
    done < <(find "${dir}" -maxdepth 1 -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.webp" \) -mmin "+${MAX_AGE_MINUTES}" -print0)
done

if [ "${deleted}" -gt 0 ]; then
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Cleaned up ${deleted} file(s) older than ${MAX_AGE_MINUTES}m from ComfyUI input/output"
fi
