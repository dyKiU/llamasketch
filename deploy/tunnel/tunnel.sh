#!/usr/bin/env bash
set -euo pipefail

CONF="/etc/llamasketch/tunnel.conf"
LOG="/var/log/llamasketch/tunnel.log"

if [[ ! -f "$CONF" ]]; then
    echo "ERROR: Config file not found: $CONF" >&2
    exit 1
fi

source "$CONF"

# Validate required vars
for var in VASTAI_HOST VASTAI_PORT VASTAI_USER VASTAI_KEY LOCAL_PORT REMOTE_PORT; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: $var not set in $CONF" >&2
        exit 1
    fi
done

if [[ ! -f "$VASTAI_KEY" ]]; then
    echo "ERROR: SSH key not found: $VASTAI_KEY" >&2
    exit 1
fi

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG"; }

log "TUNNEL START → ${VASTAI_USER}@${VASTAI_HOST}:${VASTAI_PORT} (L${LOCAL_PORT}→R${REMOTE_PORT})"

export AUTOSSH_GATETIME=0
export AUTOSSH_LOGFILE="$LOG"

exec autossh -M 0 \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -i "$VASTAI_KEY" \
    -p "$VASTAI_PORT" \
    -N -L "${LOCAL_PORT}:localhost:${REMOTE_PORT}" \
    "${VASTAI_USER}@${VASTAI_HOST}"
