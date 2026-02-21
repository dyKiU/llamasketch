#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Update LlamaSketch SSH tunnel target (Vast.ai host/port)
#
# Run from local machine when the Vast.ai instance changes.
#
# Usage: ./scripts/update-tunnel.sh <host> <port> [--key <path>]
# Examples:
#   ./scripts/update-tunnel.sh ssh7.vast.ai 34749
#   ./scripts/update-tunnel.sh 77.33.143.182 10142
#   ./scripts/update-tunnel.sh ssh4.vast.ai 28001 --key ~/secrets/llamasketch/new_key
# =============================================================================

if [[ $# -lt 2 ]]; then
    echo "Usage: update-tunnel.sh <host> <port> [--key <path>]"
    echo ""
    echo "Examples:"
    echo "  ./scripts/update-tunnel.sh ssh7.vast.ai 34749"
    echo "  ./scripts/update-tunnel.sh 77.33.143.182 10142"
    echo "  ./scripts/update-tunnel.sh ssh4.vast.ai 28001 --key ~/secrets/llamasketch/new_key"
    exit 1
fi

NEW_HOST="$1"
NEW_PORT="$2"
NEW_KEY=""

shift 2
while [[ $# -gt 0 ]]; do
    case "$1" in
        --key)
            NEW_KEY="${2:?--key requires a path argument}"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

VPS_SSH="ssh vps-3291984"
VPS_SCP="scp -o StrictHostKeyChecking=no"
VPS_SCP_TARGET="vps-3291984"
VASTAI_KEY_REMOTE="/etc/llamasketch/id_ed25519.vast.ai"

echo "============================================"
echo "Updating tunnel target → ${NEW_HOST}:${NEW_PORT}"
echo "============================================"
echo ""

# Step 1: Update config
echo "--- Step 1: Updating tunnel config ---"
${VPS_SSH} "sed -i 's/^VASTAI_HOST=.*/VASTAI_HOST=${NEW_HOST}/' /etc/llamasketch/tunnel.conf && \
            sed -i 's/^VASTAI_PORT=.*/VASTAI_PORT=${NEW_PORT}/' /etc/llamasketch/tunnel.conf"
echo "Updated /etc/llamasketch/tunnel.conf"

# Step 2: Upload new key if provided
if [[ -n "$NEW_KEY" ]]; then
    echo ""
    echo "--- Step 2: Uploading new SSH key ---"
    if [[ ! -f "$NEW_KEY" ]]; then
        echo "ERROR: Key file not found: $NEW_KEY" >&2
        exit 1
    fi
    ${VPS_SCP} "$NEW_KEY" "${VPS_SCP_TARGET}:${VASTAI_KEY_REMOTE}"
    ${VPS_SSH} "chmod 600 ${VASTAI_KEY_REMOTE}"
    echo "Uploaded new key to ${VASTAI_KEY_REMOTE}"
fi

# Step 3: Restart service
echo ""
echo "--- Step 3: Restarting tunnel service ---"
${VPS_SSH} "systemctl restart llamasketch-tunnel"
echo "Service restarted"

# Step 4: Verify
echo ""
echo "--- Step 4: Verifying ---"
sleep 3

if ${VPS_SSH} "systemctl is-active llamasketch-tunnel > /dev/null 2>&1"; then
    echo "Service: ACTIVE"
else
    echo "Service: FAILED"
    echo ""
    ${VPS_SSH} "journalctl -u llamasketch-tunnel -n 10 --no-pager"
    exit 1
fi

echo ""
echo "Testing tunnel connectivity..."
if ${VPS_SSH} "curl -sf --max-time 5 http://127.0.0.1:18188/ > /dev/null 2>&1"; then
    echo "ComfyUI reachable through tunnel!"
else
    echo "WARNING: ComfyUI not reachable at 127.0.0.1:18188"
    echo "The Vast.ai instance may still be starting up."
fi

echo ""
echo "Last 5 lines of tunnel.log:"
${VPS_SSH} "tail -5 /var/log/llamasketch/tunnel.log 2>/dev/null || echo '(no log output yet)'"

echo ""
echo "============================================"
echo "Tunnel updated to ${NEW_HOST}:${NEW_PORT}"
echo "============================================"
