# SSH Tunnel for Backend Security

## The Command

```bash
ssh -p 13273 -o ServerAliveInterval=15 root@ssh2.vast.ai -N -L 18188:localhost:18188
```

## What Each Flag Does

| Flag | Purpose |
|------|---------|
| `-p 13273` | Connect to Vast.ai's SSH gateway on port 13273 (assigned per instance) |
| `-o ServerAliveInterval=15` | Send a keepalive packet every 15 seconds to prevent the tunnel from going stale |
| `root@ssh2.vast.ai` | Authenticate to the Vast.ai SSH relay as root |
| `-N` | Don't open a shell — only forward ports (no interactive session) |
| `-L 18188:localhost:18188` | Forward local port 18188 to the remote machine's `localhost:18188` |

## How It Works

```
┌─────────────────┐          SSH tunnel           ┌──────────────────────┐
│  Your machine    │  ──────────────────────────▶  │  Vast.ai instance    │
│                  │   encrypted, authenticated    │                      │
│  localhost:18188 │ ◀──────────────────────────── │  localhost:18188     │
│  (tunnel entry)  │         port forward          │  (ComfyUI internal)  │
└─────────────────┘                                └──────────────────────┘
```

1. The SSH client opens an encrypted connection to the Vast.ai instance through `ssh2.vast.ai:13273`.
2. The `-L` flag binds port 18188 on your local machine.
3. Any traffic sent to `localhost:18188` locally gets forwarded through the encrypted tunnel to `localhost:18188` on the remote machine — where ComfyUI is listening.
4. The Python backend (FastAPI) calls `http://localhost:18188` as if ComfyUI were running locally.

## Why This Secures the Backend

### ComfyUI is never exposed to the internet

ComfyUI listens on the remote machine's `localhost:18188` — a loopback address. It does not bind to `0.0.0.0`, so no external IP can reach it directly. The only way in is through the SSH tunnel.

Without the tunnel, you'd need to either:
- Open a firewall port on the Vast.ai instance (exposes ComfyUI to the entire internet)
- Use Vast.ai's built-in proxy on port 8188 (which adds an auth layer, but that auth proxy is designed for the web UI, not API calls — and returns 401 for programmatic access)

### Authentication is handled by SSH keys

The tunnel requires your SSH private key (`~/.ssh/id_ed25519`) to establish. No password, no token, no API key sitting in an environment variable. If someone doesn't have your key, they can't open the tunnel.

### All traffic is encrypted

Every ComfyUI API call — prompt submissions, status polls, image downloads — travels through the SSH tunnel's encrypted channel. Even on an untrusted network, the data between your machine and the Vast.ai instance is protected.

### No credentials in application code

The backend simply calls `http://localhost:18188`. There are no API keys, bearer tokens, or secrets in the FastAPI code or configuration. The authentication boundary lives entirely at the SSH layer, outside the application.

### Minimal attack surface

- `-N` ensures no shell is opened — the connection exists purely for forwarding
- Only one port is forwarded (18188), limiting what's reachable
- `ServerAliveInterval=15` detects a dead connection quickly so stale tunnels don't linger

## Comparison to Alternatives

| Approach | Security | Complexity | Drawback |
|----------|----------|------------|----------|
| **SSH tunnel** (what we use) | Strong — encrypted, key-auth, no exposure | Low — one command | Must keep tunnel running |
| Expose port publicly + firewall | Weak — relies on IP allowlists | Medium | IP changes break access |
| Vast.ai auth proxy (port 8188) | Moderate — Caddy + auth | Low | Returns 401 for API calls; designed for browser, not programmatic access |
| VPN (WireGuard/Tailscale) | Strong | Higher — install + config on both ends | Overkill for single-port forwarding |

## Keeping the Tunnel Alive

The `ServerAliveInterval=15` flag sends a keepalive every 15 seconds. This prevents:
- NAT/firewall timeouts that silently kill idle connections
- The tunnel going stale during long generation jobs when no API calls are in flight

If the tunnel dies (laptop sleep, network change), just re-run the command. The backend will reconnect to `localhost:18188` on the next API call automatically — no restart needed.
