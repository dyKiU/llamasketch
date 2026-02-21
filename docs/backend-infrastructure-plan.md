# Backend Infrastructure & Pricing Strategy

> Planning document for GPU backend availability, cost optimization, and pricing tiers

---

## The Core Problem

| Factor | Challenge |
|--------|-----------|
| **Cost** | RTX 4090 ~$0.20-1.00/hr — expensive to run 24/7 |
| **Spin-up time** | Cold start: 30+ mins (model download, setup) |
| **Availability** | Stopped instances may not be reclaimable for hours/days |
| **Demand** | Unpredictable — could be 0 users or 100 at any moment |
| **User experience** | Users expect <5s response, not "please wait 30 mins" |

**Key insight:** We can never have zero instances if we want reasonable UX, but we can't afford infinite hot standby either.

---

## Instance States

```
┌─────────────────────────────────────────────────────────────────┐
│                     INSTANCE LIFECYCLE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   COLD (not rented)                                              │
│      │                                                           │
│      │ Rent + Setup (30-60 min)                                 │
│      ▼                                                           │
│   WARM (rented, stopped/paused)                                 │
│      │                                                           │
│      │ Resume (~2-5 min)                                        │
│      ▼                                                           │
│   HOT (running, ComfyUI loaded)                                 │
│      │                                                           │
│      │ Inference (~2-10 sec per image)                          │
│      ▼                                                           │
│   SERVING (actively processing jobs)                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| State | Hourly Cost | Time to Ready | Availability Risk |
|-------|-------------|---------------|-------------------|
| **Cold** | $0 | 30-60 min | High (market dependent) |
| **Warm** | ~$0.05-0.10? | 2-5 min | Low (we hold the lease) |
| **Hot** | $0.20-1.00 | Instant | None |
| **Serving** | $0.20-1.00 | N/A | None |

---

## Availability Strategy

### Minimum Viable Setup (MVP)

**1 Hot Instance Always Running**

```
Cost: ~$0.50/hr × 24hr × 30 days = ~$360/month
```

- Handles baseline traffic instantly
- No cold start for first N users
- Simple to implement
- **Risk:** Single point of failure, limited throughput

### Growth Setup

**1 Hot + 1 Warm + Auto-scale**

```
Base cost: ~$400-500/month
Peak cost: Add ~$0.50-1.00/hr per additional instance
```

| Instance | State | Purpose |
|----------|-------|---------|
| Primary | HOT | Always-on, handles all baseline traffic |
| Standby | WARM | Resume in 2-5 min when primary queue > threshold |
| Overflow | COLD | Rent on-demand during sustained spikes |

### Scale-Out Triggers

```
IF queue_depth > 10 jobs AND standby = WARM:
    Resume standby → HOT (2-5 min)

IF queue_depth > 30 jobs AND all instances HOT:
    Rent new instance from pool → COLD→HOT (30-60 min)
    
IF queue_depth < 3 jobs for 30 min AND instances > 1:
    Stop oldest non-primary instance → WARM
    
IF instance WARM for > 24 hours AND no spikes predicted:
    Consider releasing (but risk losing availability)
```

---

## Cost Modeling

### Assumptions

| Variable | Value |
|----------|-------|
| RTX 4090 spot rate | $0.40/hr average |
| RTX 4090 on-demand | $0.80/hr |
| Images per hour (saturated) | ~200-400 |
| Avg user session | 10-20 images |
| Model load time | 30-60 seconds |
| Inference time | 3-8 seconds |

### Monthly Cost Scenarios

| Scenario | Instances | Monthly Cost | Capacity |
|----------|-----------|--------------|----------|
| **Minimal** | 1 HOT (spot) | ~$290 | ~150k imgs/mo |
| **Standard** | 1 HOT + 1 WARM | ~$350-400 | ~300k imgs/mo burst |
| **Growth** | 2 HOT + 1 WARM | ~$600-700 | ~500k imgs/mo |
| **Scale** | 3 HOT + 2 WARM | ~$1,000+ | ~1M imgs/mo |

### Cost Per Image (at different utilization)

| Utilization | Images/month | Cost/month | Cost/image |
|-------------|--------------|------------|------------|
| 10% | 15,000 | $290 | $0.019 |
| 30% | 45,000 | $290 | $0.006 |
| 50% | 75,000 | $290 | $0.004 |
| 80% | 120,000 | $290 | $0.002 |
| 100%+ (need 2nd) | 200,000 | $580 | $0.003 |

**Key insight:** Cost per image drops dramatically with utilization. Need pricing that encourages usage while covering fixed costs.

---

## User Pricing Tiers

### Option A: Pay-Per-Image

| Tier | Price/Image | Included | Notes |
|------|-------------|----------|-------|
| Free | $0 | 10/day | Rate limited, queue priority: low |
| Basic | $0.02 | Pay as you go | Priority: normal |
| Pro | $0.015 | 500/mo minimum | Priority: high |
| Enterprise | $0.01 | 5000/mo minimum | Dedicated capacity |

**Pros:** Simple, scales with usage  
**Cons:** Unpredictable revenue, hard to cover fixed costs

### Option B: Subscription + Credits

| Tier | Monthly | Credits | Overage | Priority |
|------|---------|---------|---------|----------|
| **Free** | $0 | 50 imgs | N/A | Low |
| **Starter** | $9 | 500 imgs | $0.025/img | Normal |
| **Creator** | $29 | 2,000 imgs | $0.018/img | High |
| **Studio** | $99 | 10,000 imgs | $0.012/img | Highest |
| **Enterprise** | Custom | Custom | Custom | Dedicated |

**Pros:** Predictable revenue, covers baseline costs  
**Cons:** Users may feel limited

### Option C: Hybrid (Recommended)

```
Free tier:     20 imgs/day, queue priority low, watermark
Premium:       $15/mo unlimited*, priority normal, no watermark
Pro:           $49/mo unlimited*, priority high, API access
Enterprise:    Custom, dedicated GPU, SLA

* "Unlimited" = fair use ~5,000 imgs/mo, then throttled
```

**Revenue targets:**
- 100 free users (marketing) = $0
- 50 Premium @ $15 = $750/mo
- 20 Pro @ $49 = $980/mo
- Break-even: ~$400-500/mo infra = need ~30-40 paid users

---

## Queue & Priority System

```
┌─────────────────────────────────────────────────────────────────┐
│                        JOB QUEUE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   [Enterprise] ──────────────────────────────────┐              │
│   [Pro] ─────────────────────────────────────────┤              │
│   [Premium] ─────────────────────────────────────┼──► GPU 1     │
│   [Free] ────────────────────────────────────────┤   (primary)  │
│                                                   │              │
│   Overflow (queue > 20) ─────────────────────────┼──► GPU 2     │
│                                                   │   (standby)  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Priority Rules

1. **Enterprise:** Immediate, dedicated capacity if available
2. **Pro:** Next in queue after enterprise, max 30s wait
3. **Premium:** Standard queue, max 2 min wait target
4. **Free:** Back of queue, max 5 min wait, deprioritized during peaks

### Queue Overflow Handling

```python
if queue_wait_time > 60s and tier == "free":
    return "Server busy, try again in a few minutes"
    
if queue_wait_time > 120s and tier == "premium":
    spin_up_standby()  # Resume warm instance
    
if queue_wait_time > 30s and tier in ["pro", "enterprise"]:
    spin_up_overflow()  # Rent additional capacity
```

---

## Implementation Phases

### Phase 1: MVP (Week 1-2)
- [ ] Single HOT instance, always running
- [ ] Simple FIFO queue
- [ ] Manual scaling (you watch, you add)
- [ ] Free tier only (testing)

### Phase 2: Basic Scaling (Week 3-4)
- [ ] Add WARM standby instance
- [ ] Auto-resume on queue depth
- [ ] Basic priority queue (free vs paid)
- [ ] Stripe integration for subscriptions

### Phase 3: Production (Month 2)
- [ ] Multi-instance load balancing
- [ ] Auto-scale up/down
- [ ] Full tier system
- [ ] Usage tracking & billing
- [ ] SLA monitoring

### Phase 4: Optimization (Month 3+)
- [ ] Predictive scaling (time-of-day patterns)
- [ ] Spot instance bidding strategy
- [ ] Multi-region for latency
- [ ] Reserved capacity for enterprise

---

## Open Questions

1. **Vast.ai vs alternatives?** (Lambda, RunPod, self-hosted)
   - Vast.ai: cheapest, least reliable
   - RunPod: middle ground
   - Lambda: expensive, most reliable
   - Mix for redundancy?

2. **Warm instance cost?** 
   - Does Vast.ai charge for stopped instances?
   - If yes, how much? (need to verify)

3. **Image storage costs?**
   - R2/S3 for generated images
   - How long to retain?
   - User-deletable?

4. **Peak demand patterns?**
   - Need analytics before optimizing
   - Assume US daytime peaks initially

5. **Burst pricing?**
   - Charge premium during high demand?
   - Or fixed pricing, queue management only?

---

## Monitoring & Alerts

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Queue depth | > 10 | > 30 | Scale up |
| Queue wait (Pro) | > 30s | > 60s | Scale up immediately |
| Instance health | Degraded | Down | Failover |
| GPU utilization | < 20% for 1hr | < 10% for 2hr | Scale down |
| Cost/day | > $20 | > $30 | Review, notify |

---

*Created: 2026-02-21*
*Project: pencil-flux-klein / llamasketch.com*
