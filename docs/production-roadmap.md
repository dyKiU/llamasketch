# LlamaSketch.com — Production Roadmap

## Current State

Single-page vanilla JS app + FastAPI backend on a single Vast.ai RTX 4090. No auth, no persistence, no payments. Jobs stored in-memory (lost on restart). Images stored client-side in IndexedDB.

---

## Pricing & Economics

### Compute Costs (Vast.ai RTX 4090)

| Metric | Value |
|--------|-------|
| GPU rental | ~$0.30/hr ($216/mo) |
| Generation time | ~2s per image (4 steps) |
| Max throughput | ~1,800 images/hr at 100% util |
| Realistic utilization | 15–30% (users pause, think, draw) |
| Effective throughput | ~360 images/hr at 20% util |
| Cost per image (20% util) | $0.00083 |
| Cost per image (10x markup) | $0.0083 |

### Instance Spin-Up

| Step | Time |
|------|------|
| Vast.ai instance allocation | 30–120s |
| Model download (~15 GB first time) | 2–5 min |
| ComfyUI startup + warmup | 30–60s |
| **Total cold start** | **3–7 min** |
| **Warm restart** (models cached) | **~1 min** |

### Proposed Pricing

| Tier | Price | Generations | Per-gen cost | Notes |
|------|-------|-------------|--------------|-------|
| Free | $0 | 20/day | — | No account needed, IP-limited |
| Starter | $8/mo | 2,000/mo | $0.004 | Email signup |
| Pro | $20/mo | 8,000/mo | $0.0025 | Priority queue |
| Unlimited | $40/mo | Unlimited | — | Fair-use cap ~1,000/day |

**Break-even per GPU:** ~27 Pro users or ~6 Unlimited users covers one $216/mo GPU.

**Live sketch generates aggressively:** One drawing session (5 min active sketching) fires ~20 main generations + 16 variations = ~36 images. A 30-min session could produce 200+ images. Pricing must account for this.

### Revenue model alternatives to explore

- **Per-session pricing** — $0.50 per sketch session (unlimited gens within session)
- **Credit packs** — Buy 500 credits for $5 (1 credit = 1 generation)
- **Time-based** — $1/hr of active use (GPU time billed)

---

## Architecture — Current vs Production

### Current (MVP)

```
Browser → FastAPI (port 8000) → ComfyUI (port 18188) → RTX 4090
           in-memory jobs          single instance
```

### Production Target

```
                    ┌──────────────┐
                    │ Cloudflare   │
                    │ Pages / CDN  │  ← llamasketch.com (static frontend)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ API Gateway  │  ← Auth, rate limiting, routing
                    │ (Edge/CF     │
                    │  Workers)    │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │    API Server(s)        │  ← FastAPI, stateless
              │    (Fly.io / Railway)   │
              └────────────┬────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                 ▼
   ┌──────────┐    ┌──────────┐     ┌──────────┐
   │ Postgres │    │  Redis   │     │ R2 / S3  │
   │ (users,  │    │ (job     │     │ (images) │
   │  billing,│    │  queue)  │     │          │
   │  quotas) │    │          │     │          │
   └──────────┘    └────┬─────┘     └──────────┘
                        │
              ┌─────────▼──────────┐
              │  GPU Worker Pool   │  ← Vast.ai instances
              │  ┌─────┐ ┌─────┐  │     (ComfyUI + FastAPI worker)
              │  │GPU 1│ │GPU 2│  │     Auto-scale 1–N
              │  └─────┘ └─────┘  │
              └────────────────────┘
```

---

## Milestones

### Phase 1: Polish & Ship (pre-revenue)

- [ ] **P1.1: UI polish pass** — Loading states, error toasts, mobile layout fixes, favicon, OG meta tags, onboarding tooltip ("draw something!")
- [ ] **P1.2: Landing page** — Hero demo, pricing table, "Try free" CTA. Separate from the app page.
- [ ] **P1.3: Domain + hosting** — llamasketch.com pointed at Cloudflare Pages (static) + API subdomain (api.llamasketch.com)
- [ ] **P1.4: Prompt library** — Curated prompt suggestions / autocomplete to help new users get good results fast
- [ ] **P1.5: Gallery / showcase** — Public gallery of best generations to attract users

### Phase 2: Auth & Accounts

- [ ] **P2.1: Auth provider** — Clerk or Supabase Auth. Email + Google OAuth. JWT tokens.
- [ ] **P2.2: API auth middleware** — Validate JWT on every `/api/generate` call. Reject unauthenticated requests (except free tier via fingerprint/IP).
- [ ] **P2.3: User table** — Postgres: `users(id, email, plan, credits_remaining, created_at)`
- [ ] **P2.4: Quota enforcement** — Check credits before generation. Decrement on completion (not on submit — failed jobs don't cost).
- [ ] **P2.5: Account page** — Usage dashboard, plan info, upgrade CTA

### Phase 3: Payments

- [ ] **P3.1: Stripe integration** — Products + prices for each tier. Checkout sessions.
- [ ] **P3.2: Webhook handler** — `invoice.paid` → credit account, `customer.subscription.deleted` → downgrade
- [ ] **P3.3: Billing portal** — Stripe Customer Portal link for managing subscription
- [ ] **P3.4: Free tier limits** — Rate limit by IP/fingerprint. Show upgrade prompt when limit hit.
- [ ] **P3.5: Usage metering** — Track generations per billing period. Overage handling (soft cap + warning vs hard cutoff).
- [ ] **P3.6: Lightning Network payments** — Bitcoin/Lightning micropayments as alternative to Stripe. Separate project/repo. Pay-per-generation model (sats per image) fits Lightning perfectly. See `docs/lightning-payments.md`.
- [ ] **P3.7: Web3 wallet / USDT on Liquid** — Accept USDT (stablecoin) and L-BTC via Liquid Network. Compatible with Aqua, Green, SideSwap wallets. Eliminates BTC volatility concern. See `docs/lightning-payments.md`.
- [ ] **P3.8: Unified payment modal** — Single top-up UI offering Card / Lightning / USDT. All rails credit the same internal ledger.

### Phase 4: Persistent Storage

- [ ] **P4.1: Image storage** — Cloudflare R2 or S3. Upload result PNGs on completion. Signed URLs for retrieval.
- [ ] **P4.2: Server-side sessions** — Replace IndexedDB-only storage. `sessions(id, user_id, created_at)` + `images(id, session_id, r2_key, created_at)`
- [ ] **P4.3: Cross-device sync** — User logs in on new device, sees their history
- [ ] **P4.4: Storage limits** — Free: 50 images retained (30 days). Pro: 5,000 images (90 days). Unlimited: 20,000 images (1 year).
- [ ] **P4.5: Export** — ZIP download of full session (already works client-side, add server-side for cross-device)

### Phase 5: Compute Infrastructure

- [ ] **P5.1: Worker process** — Decouple API from GPU. API writes job to Redis queue. Separate worker process on GPU instance pulls from queue, runs ComfyUI, writes result to R2.
- [ ] **P5.2: Health monitoring** — Cron job pings each GPU instance every 30s. Mark unhealthy after 3 failures. Auto-replace.
- [ ] **P5.3: GPU health check on boot** — Run `gpu_health_check.py` before accepting jobs. Reject defective instances automatically.
- [ ] **P5.4: Auto-scaling** — Monitor queue depth. If avg wait > 5s, spin up another instance. If idle > 15 min, spin down. Min 1 warm instance during business hours.
- [ ] **P5.5: Instance pooling** — Pre-provision 2 instances (1 active, 1 standby). Rotate standby to active on failure. Replace standby in background.
- [ ] **P5.6: Model caching** — Vast.ai persistent storage volume with models pre-downloaded. Cuts cold start from 5 min to ~1 min.
- [ ] **P5.7: Multi-region** — Eventually: US-East + EU instances. Route users to nearest.

### Phase 6: Reliability & Monitoring

- [ ] **P6.1: Structured logging** — JSON logs from API and workers. Ship to Datadog/Grafana Cloud.
- [ ] **P6.2: Error tracking** — Sentry for both backend (Python) and frontend (JS).
- [ ] **P6.3: Metrics** — Generation latency (p50/p95/p99), queue depth, GPU utilization, error rate, active users.
- [ ] **P6.4: Alerting** — PagerDuty/Slack alerts on: all GPUs unhealthy, error rate > 5%, queue depth > 50.
- [ ] **P6.5: Graceful degradation** — When no GPUs available: show "busy" message with ETA, queue position, option to get email notification when ready.

---

## Open Questions

1. **Vast.ai vs dedicated GPU** — Vast.ai is cheap but unreliable (defective GPUs, interruptions, inconsistent availability). At what user count does a dedicated A10/A100 on Lambda/CoreWeave make sense? (~$1.10/hr for A100 = $792/mo, but rock-solid)
2. **Shared vs dedicated GPUs** — Can multiple users share one GPU? ComfyUI processes one job at a time. Queue depth > 1 means latency for live sketch. May need 1 GPU per ~3–5 concurrent users.
3. **Model updates** — FLUX.2 is evolving. How to deploy new models without downtime? Blue/green on Vast.ai is tricky.
4. **NSFW filtering** — Need content moderation for generated images if there's a public gallery. Options: CLIP-based classifier, external API (AWS Rekognition), or manual review queue.
5. **IP / legal** — Terms of service, generated image ownership, FLUX.2 license implications for commercial use.
7. **Client-side encryption** — Users hold their own keys for image privacy. See `work-stack.md`. Trade-off: encrypted images can't be thumbnailed or moderated server-side.
6. **Concurrency model** — Live sketch fires generations on every stroke pause. If 10 users are sketching simultaneously, that's 10+ jobs/sec. Need to model queue behavior and set expectations (latency vs throughput).

---

## Priority Order (suggested)

Ship in this order to get revenue flowing:

1. **P1** (polish) — 1 week — Make it look real
2. **P2** (auth) — 1 week — Know who users are
3. **P3** (payments) — 1 week — Start charging
4. **P4** (storage) — 1 week — Retain users across devices
5. **P5** (infra) — 2 weeks — Scale beyond 1 GPU
6. **P6** (monitoring) — ongoing — Sleep at night
