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

## How the Frontend Talks to the API (No HTTPS Needed)

The frontend (`static/index.html`) makes API calls with a relative path:

```js
const API = '';
fetch(`${API}/api/generate`, { ... })
// resolves to e.g. http://localhost:8000/api/generate
```

The full request chain looks like this:

```
┌──────────┐         ┌──────────────┐        SSH tunnel         ┌──────────────────┐
│  Browser  │  HTTP   │  FastAPI     │  HTTP (inside tunnel)     │  ComfyUI         │
│           │ ──────▶ │  localhost   │ ──────────────────────▶   │  Vast.ai         │
│           │         │  :8000       │                           │  localhost:18188  │
└──────────┘         └──────────────┘                           └──────────────────┘
     localhost             localhost                                  localhost
     (browser)             (backend)                               (remote, tunneled)
```

Every hop is `localhost`. The browser talks to the local FastAPI server over plain HTTP on `localhost:8000`. The FastAPI server talks to ComfyUI on `localhost:18188` — which is actually the tunnel entrance. The tunnel encrypts everything from there to the Vast.ai instance.

### Why no TLS/HTTPS certificates are needed

- **Browser to FastAPI**: Both run on your machine. The traffic never leaves `localhost`, so there's nothing to intercept. Browsers don't require HTTPS for `localhost`.
- **FastAPI to ComfyUI**: The SSH tunnel handles encryption. SSH uses its own cryptographic protocol (not TLS) with key exchange (Curve25519), encryption (ChaCha20-Poly1305 or AES-GCM), and integrity checks — all established automatically when the tunnel opens. No certificate authority, no certificate renewal, no Let's Encrypt.

### SSH encryption vs TLS certificates

| | SSH tunnel | TLS/HTTPS |
|---|---|---|
| **Identity verification** | SSH host key fingerprint (verified on first connect, then cached in `~/.ssh/known_hosts`) | Certificate signed by a Certificate Authority |
| **Authentication** | Your Ed25519 private key | Client certificates (rare) or application-layer tokens |
| **Encryption** | ChaCha20-Poly1305 / AES-256-GCM | AES-256-GCM (same algorithms, different protocol) |
| **Certificate management** | None — just your SSH key pair | Must obtain, install, and renew certificates |
| **Trust model** | Trust-on-first-use (TOFU) — you verify the host key once | Trust the CA hierarchy |

SSH is not "less secure" than TLS — it just uses a different trust model. For a single-developer setup tunneling to a known server, SSH key authentication is simpler and equally strong.

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

## Vast.ai Server Security

Vast.ai is a GPU marketplace — you're renting hardware from a mix of providers. Security varies significantly depending on the provider tier.

### What Vast.ai provides

- **Container isolation**: Workloads run in unprivileged Docker containers with separate namespaces, cgroups, and filesystem isolation. Other tenants on the same physical machine cannot access your container.
- **SSH relay**: Connections go through `ssh2.vast.ai` (a relay), not directly to the host's public IP. The relay handles routing to the correct container.
- **Secure Cloud tier**: Vetted datacenter partners with ISO 27001 certification minimum. Many also hold HIPAA, NIST, PCI, SOC 1-3, and GDPR compliance. Physical security, access controls, and regular audits.

### What Vast.ai does NOT provide

- **No encryption at rest**: Your data on the instance disk is not automatically encrypted. If you store sensitive data, encrypt it yourself before uploading.
- **No guaranteed network controls**: Firewall capability depends on the host provider's configuration. Not all providers offer the same level of network isolation.
- **No sandboxing for untrusted code**: The platform is designed for trusted team environments. There's no syscall filtering or container-level hardening beyond standard Docker isolation.
- **Provider access varies**: On lower-tier (non-Secure-Cloud) providers, the host operator could theoretically inspect container contents. On Secure Cloud partners, this is governed by data processing agreements and audits.

### What this means for us

Our setup mitigates most of these concerns:

| Vast.ai risk | Our mitigation |
|---|---|
| No encryption at rest | We only store model weights (public) and temporary generation outputs |
| Multi-tenant host | ComfyUI binds to localhost only — other containers can't reach it even on the same host |
| Provider could inspect disk | No secrets on the instance — SSH keys live on our machine, not the server |
| Network exposure | SSH tunnel means zero ports exposed publicly; ComfyUI is loopback-only |

The key insight: the Vast.ai instance is treated as an **untrusted compute node**. All trust lives on our local machine (SSH keys, application code, user data). The instance just runs ComfyUI and returns pixels through an encrypted pipe.

### Sources

- [Vast.ai Security FAQ](https://docs.vast.ai/documentation/reference/faq/security)
- [Running Private AI Models Without Data Exposure](https://vast.ai/article/running-private-ai-models-without-the-risk-of-data-exposure)
- [Vast.ai Compliance](https://vast.ai/compliance)
