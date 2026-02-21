# LlamaSketch — Server Setup Guide

> Sensitive info (IPs, SSH keys, ports, passwords) is in `~/secrets/llamasketch/server.md` — **not** in this repo.

## Overview

LlamaSketch runs on a shared InterServer VPS alongside other projects. The architecture:

```
Internet
  |
  +--> nginx (host, port 80/443, SSL termination)
         |
         +--> staging.llamasketch.com --> Docker container (staging, port 8100)
         +--> llamasketch.com         --> Docker container (prod, port 8200)
         +--> (other sites on same server)
```

GPU inference runs on a separate Vast.ai instance — the VPS only runs the FastAPI web app.

---

## Prerequisites

On the server:
- **nginx** (`sudo apt install nginx`)
- **certbot** + nginx plugin (`sudo apt install certbot python3-certbot-nginx`)
- **Docker** + Docker Compose (`docs.docker.com/engine/install/ubuntu/`)
- **git** (`sudo apt install git`)
- **UFW firewall** allowing ports 80, 443, and your SSH port

On your local machine:
- SSH key with access to the server (see `~/secrets/llamasketch/server.md`)
- Git push access to the repo

---

## DNS Setup

Before anything else, create A records at your DNS provider:

```
staging.llamasketch.com  A  <server-ip>
llamasketch.com          A  <server-ip>
www.llamasketch.com      A  <server-ip>
```

Wait for propagation (check with `dig staging.llamasketch.com`).

---

## Containerization

**Decision: Yes, containerize.** Rationale:

- The VPS hosts multiple projects — Docker isolates each one
- Same image runs on staging and prod, only `.env` differs
- Rollback is trivial: rebuild from a previous git commit
- Negligible overhead (~50 MB image, FastAPI is lightweight)
- No build step for the frontend (vanilla JS) — just copy static files

The **Dockerfile** and **docker-compose.yml** are in the project root.

---

## Deployment Steps

### 1. SSH to the server

```bash
ssh -i <key> -p <port> <user>@<ip>
# See ~/secrets/llamasketch/server.md for actual values
```

### 2. Clone the repo (first time only)

```bash
cd /home/<user>
git clone <repo-url> llamasketch
cd llamasketch
```

### 3. Create the `.env` file

```bash
# Staging
cp .env.staging.example .env

# OR Production
cp .env.prod.example .env
```

Edit `.env` and fill in the actual Vast.ai ComfyUI URL. See `~/secrets/llamasketch/server.md` for values.

Key difference between staging and prod:

| Variable | Staging | Production |
|----------|---------|------------|
| `PENCIL_PORT` | 8100 | 8200 |
| `PENCIL_SIGNUP_ENABLED` | true | false |

### 4. Build and start

```bash
docker compose build
docker compose up -d
```

Verify:

```bash
curl http://127.0.0.1:<port>/api/health
```

### 5. Set up nginx (HTTP-only first)

```bash
# Staging
sudo cp deploy/nginx/staging.llamasketch.com.http.conf \
  /etc/nginx/sites-available/staging.llamasketch.com
sudo ln -sf /etc/nginx/sites-available/staging.llamasketch.com \
  /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

```bash
# Production
sudo cp deploy/nginx/llamasketch.com.http.conf \
  /etc/nginx/sites-available/llamasketch.com
sudo ln -sf /etc/nginx/sites-available/llamasketch.com \
  /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 6. Generate SSL certificates

```bash
# Staging
sudo certbot --nginx \
  -d staging.llamasketch.com \
  --non-interactive --agree-tos \
  --email admin@llamasketch.com \
  --redirect

# Production
sudo certbot --nginx \
  -d llamasketch.com -d www.llamasketch.com \
  --non-interactive --agree-tos \
  --email admin@llamasketch.com \
  --redirect
```

Certbot will:
1. Verify domain ownership via HTTP-01 challenge (needs port 80 open)
2. Obtain a Let's Encrypt certificate (free, auto-renews every 90 days)
3. Modify the nginx config to add `ssl_certificate` / `ssl_certificate_key` directives
4. Add HTTP-to-HTTPS redirect

### 7. (Optional) Replace with hand-written HTTPS config

Certbot's auto-generated config works fine, but if you prefer the configs in `deploy/nginx/` that include security headers:

```bash
sudo cp deploy/nginx/staging.llamasketch.com.conf \
  /etc/nginx/sites-available/staging.llamasketch.com
sudo cp deploy/nginx/llamasketch.com.conf \
  /etc/nginx/sites-available/llamasketch.com
sudo nginx -t && sudo systemctl reload nginx
```

### 8. Verify everything

```bash
# SSL working
curl -I https://staging.llamasketch.com
curl -I https://llamasketch.com

# App responding
curl https://staging.llamasketch.com/api/health
curl https://llamasketch.com/api/config
# Should show {"signup_enabled": false} on prod
```

---

## SSL Certificate Management

### Check status

```bash
sudo certbot certificates
```

### Test renewal

```bash
sudo certbot renew --dry-run
```

### Auto-renewal

Certbot sets up a systemd timer automatically. Verify:

```bash
systemctl list-timers | grep certbot
```

If missing, add a cron job:

```bash
(sudo crontab -l 2>/dev/null; echo '0 12 * * * /usr/bin/certbot renew --quiet') | sudo crontab -
```

---

## Updating the App

### Quick deploy from local machine

```bash
git push origin master
ssh -i <key> -p <port> <user>@<ip> \
  "cd /home/<user>/llamasketch && git pull && docker compose build && docker compose up -d"
```

### Rollback

```bash
# On server
cd /home/<user>/llamasketch
git log --oneline -5
git checkout <previous-commit>
docker compose build && docker compose up -d
```

---

## Running Staging and Production Side by Side

To run both on the same server, use separate docker-compose project names:

```bash
# Staging (uses .env with PENCIL_PORT=8100)
docker compose -p llamasketch-staging up -d

# Production (uses .env.prod with PENCIL_PORT=8200)
docker compose --env-file .env.prod -p llamasketch-prod up -d
```

Each gets its own container, own port, own nginx server block.

---

## Signup Gating

The `PENCIL_SIGNUP_ENABLED` env var controls whether signup is available:

- **Staging** (`true`): Signup UI visible, useful for testing auth flows
- **Production** (`false`): Signup hidden, returns 403 if called directly

The frontend reads this from `GET /api/config` on load. No code changes needed to toggle — just update `.env` and restart the container.

---

## Firewall

Ensure UFW allows web traffic:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

SSH port should already be allowed from initial server setup.

---

## Troubleshooting

| Problem | Check |
|---------|-------|
| Container won't start | `docker compose logs -f` |
| 502 Bad Gateway | `docker compose ps` — is container running? Port match in nginx vs `.env`? |
| SSL cert won't generate | DNS A records pointing to server? Port 80 open? `cat /var/log/letsencrypt/letsencrypt.log` |
| Nginx config error | `sudo nginx -t` |
| App works on HTTP but not HTTPS | `sudo certbot certificates` — cert exists? `sudo systemctl reload nginx` |
