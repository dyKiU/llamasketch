#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Deploy to Vast.ai instance — single command from local machine
#
# Usage: ./scripts/deploy.sh <host> <port> [ssh_key]
# Example: ./scripts/deploy.sh 74.48.78.46 21151 ~/.ssh/id_ed25519
# =============================================================================

HOST="${1:?Usage: deploy.sh <host> <port> [ssh_key]}"
PORT="${2:?Usage: deploy.sh <host> <port> [ssh_key]}"
SSH_KEY="${3:-$HOME/.ssh/id_ed25519}"

SSH_CMD="ssh -p ${PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=no root@${HOST}"
SCP_CMD="scp -P ${PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=no"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "============================================"
echo "Deploying to ${HOST}:${PORT}"
echo "============================================"

# Step 1: Copy files to instance
echo ""
echo "--- Step 1: Copying files to instance ---"
${SCP_CMD} \
    "${PROJECT_DIR}/scripts/gpu_health_check.py" \
    "${PROJECT_DIR}/scripts/setup_vastai.sh" \
    "${PROJECT_DIR}/scripts/test_inference.py" \
    "${PROJECT_DIR}/workflow_template.json" \
    "root@${HOST}:/workspace/"
echo "Files copied."

# Step 2: GPU health check
echo ""
echo "--- Step 2: GPU health check ---"
${SSH_CMD} "source /venv/main/bin/activate && python3 /workspace/gpu_health_check.py"
GPU_OK=$?
if [ ${GPU_OK} -ne 0 ]; then
    echo ""
    echo "ERROR: GPU health check FAILED. This instance has a defective GPU."
    echo "Rent a different instance and try again."
    exit 1
fi

# Step 3: Run setup (PyTorch upgrade + model downloads)
echo ""
echo "--- Step 3: Running setup ---"
${SSH_CMD} "source /venv/main/bin/activate && bash /workspace/setup_vastai.sh"

# Step 4: Restart ComfyUI to load new PyTorch + models
echo ""
echo "--- Step 4: Restarting ComfyUI ---"
${SSH_CMD} "supervisorctl restart comfyui && sleep 5"

# Step 5: Wait for ComfyUI to be ready
echo ""
echo "--- Step 5: Waiting for ComfyUI to start ---"
for i in $(seq 1 60); do
    if ${SSH_CMD} "curl -s --max-time 3 http://127.0.0.1:18188/ > /dev/null 2>&1"; then
        echo "ComfyUI is ready (after ${i}s)"
        break
    fi
    if [ ${i} -eq 60 ]; then
        echo "WARNING: ComfyUI did not start within 60s. Continuing anyway..."
    fi
    sleep 1
done

# Step 6: Run inference tests
echo ""
echo "--- Step 6: Running inference tests ---"
${SSH_CMD} "source /venv/main/bin/activate && cd /workspace && python3 test_inference.py --workflow /workspace/workflow_template.json"
TEST_OK=$?

echo ""
echo "============================================"
if [ ${TEST_OK} -eq 0 ]; then
    echo "DEPLOYMENT SUCCESSFUL — All tests passed!"
else
    echo "DEPLOYMENT INCOMPLETE — Some tests failed (exit code ${TEST_OK})"
fi
echo "============================================"
echo ""
echo "Instance: ssh -p ${PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=no root@${HOST}"
exit ${TEST_OK}
