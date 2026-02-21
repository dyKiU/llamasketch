#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# One-time VPS setup for LlamaSketch SSH tunnel to Vast.ai
#
# Run from local machine. SSHes to VPS automatically.
# Idempotent — safe to re-run.
#
# Usage: ./scripts/setup-tunnel.sh [vastai_host] [vastai_port]
# Example: ./scripts/setup-tunnel.sh ssh7.vast.ai 34749
# =============================================================================

VASTAI_HOST="${1:-ssh7.vast.ai}"
VASTAI_PORT="${2:-34749}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

VPS_SSH="ssh vps-3291984"
VPS_SCP="scp -o StrictHostKeyChecking=no"

# Resolve VPS SSH details for scp (read from ssh config)
VPS_SCP_TARGET="vps-3291984"

VASTAI_KEY_LOCAL="$HOME/secrets/llamasketch/id_ed25519.vast.ai"
VASTAI_KEY_REMOTE="/etc/llamasketch/id_ed25519.vast.ai"

echo "============================================"
echo "LlamaSketch Tunnel — VPS Setup"
echo "============================================"
echo ""

# Step 0: Check local prerequisites
echo "--- Step 0: Checking prerequisites ---"
if [[ ! -f "$VASTAI_KEY_LOCAL" ]]; then
    echo "Vast.ai SSH key not found at: $VASTAI_KEY_LOCAL"
    echo ""
    echo "To create it, copy your key that authenticates to Vast.ai:"
    echo "  cp ~/.ssh/id_ed25519 ~/secrets/llamasketch/id_ed25519.vast.ai"
    echo "  cp ~/.ssh/id_ed25519.pub ~/secrets/llamasketch/id_ed25519.vast.ai.pub"
    exit 1
fi
echo "Found Vast.ai SSH key: $VASTAI_KEY_LOCAL"

# Step 1: Install autossh on VPS
echo ""
echo "--- Step 1: Installing autossh on VPS ---"
${VPS_SSH} "which autossh > /dev/null 2>&1 && echo 'autossh already installed' || (apt-get update -qq && apt-get install -y -qq autossh && echo 'autossh installed')"

# Step 2: Create directories on VPS
echo ""
echo "--- Step 2: Creating directories ---"
${VPS_SSH} "mkdir -p /etc/llamasketch /var/log/llamasketch"

# Step 3: Upload tunnel wrapper script
echo ""
echo "--- Step 3: Uploading tunnel.sh ---"
${VPS_SCP} "${PROJECT_DIR}/deploy/tunnel/tunnel.sh" "${VPS_SCP_TARGET}:/etc/llamasketch/tunnel.sh"
${VPS_SSH} "chmod +x /etc/llamasketch/tunnel.sh"
echo "Uploaded /etc/llamasketch/tunnel.sh"

# Step 4: Upload systemd unit
echo ""
echo "--- Step 4: Uploading systemd unit ---"
${VPS_SCP} "${PROJECT_DIR}/deploy/systemd/llamasketch-tunnel.service" "${VPS_SCP_TARGET}:/etc/systemd/system/llamasketch-tunnel.service"
echo "Uploaded /etc/systemd/system/llamasketch-tunnel.service"

# Step 5: Upload Vast.ai SSH key
echo ""
echo "--- Step 5: Uploading Vast.ai SSH key ---"
${VPS_SCP} "${VASTAI_KEY_LOCAL}" "${VPS_SCP_TARGET}:${VASTAI_KEY_REMOTE}"
${VPS_SSH} "chmod 600 ${VASTAI_KEY_REMOTE}"
echo "Uploaded ${VASTAI_KEY_REMOTE} (chmod 600)"

# Step 6: Create tunnel config
echo ""
echo "--- Step 6: Creating tunnel config ---"
${VPS_SSH} "cat > /etc/llamasketch/tunnel.conf << 'CONF'
# Vast.ai SSH tunnel configuration
VASTAI_HOST=${VASTAI_HOST}
VASTAI_PORT=${VASTAI_PORT}
VASTAI_USER=root
VASTAI_KEY=${VASTAI_KEY_REMOTE}
LOCAL_PORT=18188
REMOTE_PORT=18188
CONF"
echo "Created /etc/llamasketch/tunnel.conf (target: ${VASTAI_HOST}:${VASTAI_PORT})"

# Step 7: Setup logrotate
echo ""
echo "--- Step 7: Setting up log rotation ---"
${VPS_SSH} "cat > /etc/logrotate.d/llamasketch-tunnel << 'LOGROTATE'
/var/log/llamasketch/tunnel.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
LOGROTATE"
echo "Log rotation configured (daily, 7 days, compress)"

# Step 8: Enable and start service
echo ""
echo "--- Step 8: Enabling and starting service ---"
${VPS_SSH} "systemctl daemon-reload && systemctl enable llamasketch-tunnel && systemctl restart llamasketch-tunnel"
echo "Service enabled and started"

# Step 9: Verify
echo ""
echo "--- Step 9: Verifying ---"
sleep 3
${VPS_SSH} "systemctl is-active llamasketch-tunnel && echo 'Service: ACTIVE' || echo 'Service: FAILED'"
echo ""
echo "Last 5 lines of tunnel.log:"
${VPS_SSH} "tail -5 /var/log/llamasketch/tunnel.log 2>/dev/null || echo '(no log output yet)'"

echo ""
echo "--- Step 10: Testing tunnel connectivity ---"
if ${VPS_SSH} "curl -sf --max-time 5 http://127.0.0.1:18188/ > /dev/null 2>&1"; then
    echo "ComfyUI reachable through tunnel!"
else
    echo "WARNING: ComfyUI not reachable at 127.0.0.1:18188"
    echo "This is expected if the Vast.ai instance is not running yet."
    echo "Check with: ssh vps-3291984 'journalctl -u llamasketch-tunnel -n 20'"
fi

echo ""
echo "============================================"
echo "Setup complete!"
echo "============================================"
echo ""
echo "Manage tunnel:"
echo "  Status:  ssh vps-3291984 'systemctl status llamasketch-tunnel'"
echo "  Logs:    ssh vps-3291984 'journalctl -u llamasketch-tunnel -f'"
echo "  Update:  ./scripts/update-tunnel.sh <host> <port>"
