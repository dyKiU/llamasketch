# Docker Host Networking for SSH Tunnel Access

## Problem

The LlamaSketch backend (FastAPI in Docker) needs to reach ComfyUI on the Vast.ai GPU instance. An `autossh` tunnel runs on the VPS host, forwarding `localhost:18188` to the remote ComfyUI. The Docker container must reach this tunnel.

## What was tried

### Attempt 1: Bridge networking + `extra_hosts` (FAILED)

Added `extra_hosts: host.docker.internal:host-gateway` to `docker-compose.yml` and set `PENCIL_COMFYUI_URL=http://host.docker.internal:18188` in `.env`.

**Result**: `host.docker.internal` resolved to `172.17.0.1` (docker0 bridge IP) inside the container, but connections timed out.

**Root cause**: Docker Compose creates a **project-specific bridge network** (e.g., `172.18.0.0/16` on `br-95ce0b843ce7`), not the default `docker0` bridge (`172.17.0.0/16`). Traffic from the container to `172.17.0.1` crosses bridge boundaries and gets blocked by iptables.

### Attempt 2: Bind tunnel to 0.0.0.0 (FAILED)

Changed `tunnel.sh` to bind the SSH tunnel on `0.0.0.0:18188` instead of `127.0.0.1:18188`. Verified with `ss -tlnp` that the tunnel was listening on all interfaces.

**Result**: From the host, `curl http://172.17.0.1:18188/` worked. From inside the container, still timed out.

**Root cause**: Same cross-bridge iptables issue. The container's traffic to `172.17.0.1` goes through Docker's `FORWARD` chain and `DOCKER-BRIDGE` chain, where it gets dropped by Docker's isolation rules.

### Attempt 3: UFW + direct iptables rules (FAILED)

Added:
- `ufw allow from 172.17.0.0/16 to any port 18188`
- `iptables -I INPUT 1 -s 172.17.0.0/16 -p tcp --dport 18188 -j ACCEPT`

**Result**: Still timed out. The iptables INPUT rule showed 0 packets matched — traffic from the compose network container never reached the INPUT chain because it was being dropped in the FORWARD chain by Docker's own isolation rules.

### Attempt 4: `network_mode: host` (SUCCESS)

Changed `docker-compose.yml` to use `network_mode: host`, removed `ports` mapping and `extra_hosts`. Updated `Dockerfile` CMD to use `$PENCIL_PORT` env var so the app listens on the correct port (8100 staging / 8200 prod) directly on the host network.

```yaml
services:
  app:
    build: .
    env_file: .env
    network_mode: host
    restart: unless-stopped
```

```dockerfile
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PENCIL_PORT:-8000}
```

**Result**: `comfyui_reachable: true`. The container shares the host's network namespace, so `127.0.0.1:18188` (the SSH tunnel) is directly reachable with zero routing complexity.

## Why `network_mode: host` works

With host networking, the container does not get its own network namespace. It shares the host's:
- `127.0.0.1` is the same loopback
- No bridge, no NAT, no iptables rules between container and host
- `ports` directive is ignored (the app binds directly to host ports)
- The app must listen on the correct port via `PENCIL_PORT` env var

## Trade-offs

| | Bridge (default) | Host |
|---|---|---|
| Port isolation | Container ports are private | App binds directly to host ports |
| Tunnel access | Requires firewall/routing config | Just works (shared loopback) |
| Port conflicts | None (mapped) | App port must not conflict with host services |
| Security | Network namespace isolation | App sees all host network traffic |

For LlamaSketch, host networking is the right choice: the VPS runs a single app, port conflicts aren't an issue, and the SSH tunnel accessibility is critical.

## Key lesson

Docker Compose project networks (`br-*`) are **not** the default `docker0` bridge. `host.docker.internal:host-gateway` resolves to the docker0 bridge IP (`172.17.0.1`), but traffic from a compose network to that IP crosses bridges and gets blocked by Docker's iptables isolation rules. This is not fixable with simple UFW/iptables rules on the INPUT chain because Docker drops the traffic in the FORWARD chain before it reaches INPUT.
