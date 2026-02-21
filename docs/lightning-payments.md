# Crypto Payments — Separate Project

Three payment rails for LlamaSketch: **Stripe** (fiat), **Lightning Network** (BTC), and **Web3 wallet** (USDT/Liquid BTC). Stripe is the default; crypto options are alternatives for privacy-conscious or unbanked users.

---

## Payment Rails Overview

| Rail | Currency | Settlement | Fees | Account needed |
|------|----------|-----------|------|----------------|
| Stripe | USD/EUR/fiat | 2-day payout | ~2.9% + $0.30 | Email + card |
| Lightning (BTC) | Sats (BTC) | Instant | Routing fees (~1 sat) | None — scan QR |
| Web3 / Aqua wallet | USDT (Liquid) or L-BTC | ~2 min (Liquid) | ~$0.01 | Wallet app only |

### Why multiple rails?

- **Stripe** — Familiar, covers 90% of users. Subscriptions, card-on-file, Apple/Google Pay.
- **Lightning** — Micropayments fit perfectly for pay-per-generation. No chargebacks. Global access without bank account.
- **Web3 / Aqua** — Stablecoin (USDT) removes BTC volatility concern. Liquid Network gives near-instant settlement with Bitcoin-grade security. Aqua wallet specifically supports both Lightning and Liquid in one app.

---

## Lightning Network

### Why Lightning

- **Micropayments fit perfectly** — Pay 50–500 sats per generation (~$0.002–$0.02). No minimum purchase, no subscription commitment.
- **No chargebacks** — Settled instantly, irreversible. Critical for a service that burns GPU time immediately.
- **Global access** — No bank account needed. Users in countries without Stripe support can pay.
- **Privacy** — No email or credit card required. Just scan and draw.
- **Instant settlement** — No 2-day Stripe payout delay.

## Pricing in Sats

At current BTC ~$95,000 (Feb 2026):

| Action | USD equivalent | Sats |
|--------|---------------|------|
| 1 generation | $0.005 | ~50 sats |
| 1 live sketch session (~36 gens) | $0.18 | ~1,800 sats |
| Bulk 128 variations | $0.64 | ~6,400 sats |
| "Day pass" (unlimited, 24h) | $2.00 | ~20,000 sats |

**Note:** Sat pricing should float with BTC/USD to keep USD-equivalent stable. Fetch rate from exchange API on each invoice.

## Architecture

```
Browser                    LlamaSketch API           Lightning Node
   │                            │                         │
   │  POST /api/invoice         │                         │
   │  { generations: 10 }       │                         │
   │ ──────────────────────────>│                         │
   │                            │  createInvoice(500 sat) │
   │                            │ ───────────────────────>│
   │                            │  <── bolt11 invoice     │
   │  <── { bolt11, payment_id }│                         │
   │                            │                         │
   │  [User pays via wallet]    │                         │
   │                            │  webhook: invoice.paid  │
   │                            │ <───────────────────────│
   │                            │  credit user 10 gens    │
   │                            │                         │
   │  POST /api/generate        │                         │
   │  { payment_id, sketch... } │                         │
   │ ──────────────────────────>│                         │
   │                            │  [check credits, run]   │
```

## Implementation Options

### Option A: LNbits (self-hosted)

- Free, open source
- REST API for creating invoices, checking payment status
- Can run alongside the API server
- Connects to your own Lightning node (or hosted node via LND/CLN)
- **Pros:** Full control, no fees beyond routing
- **Cons:** Must run a Lightning node (or use a custodial backend like LNbits + LndHub)

### Option B: Strike API / Voltage

- Managed Lightning infrastructure
- REST API, webhooks on payment
- ~1% fee
- **Pros:** No node management
- **Cons:** Custodial, KYC required for merchant account

### Option C: BTCPay Server

- Self-hosted, non-custodial
- Supports Lightning + on-chain
- Has a well-documented API
- **Pros:** Battle-tested, non-custodial, plugin ecosystem
- **Cons:** Heavier to deploy (needs Bitcoin full node or pruned)

### Recommended: Start with LNbits

Lightweight, pairs well with a hosted LND node (Voltage, $10/mo). Can migrate to BTCPay Server later if volume justifies it.

## UX Flow

1. User draws a sketch (free tier: 20 gens, no payment needed)
2. Hits free limit → modal: "Top up with Lightning?"
3. Options: 50 gens (2,500 sats) / 200 gens (8,000 sats) / Day pass (20,000 sats)
4. Shows QR code (BOLT11 invoice) + copy button
5. User scans with any Lightning wallet (Phoenix, Breez, Wallet of Satoshi, etc.)
6. Payment confirms in ~1 second
7. Credits appear instantly, user continues drawing

**No account needed.** Credits tied to a browser fingerprint / localStorage token. Optional email for cross-device recovery.

## Separate Repo

This will be a standalone microservice:

```
llamasketch-lightning/
  ├── src/
  │   ├── server.ts          # Express/Hono API
  │   ├── lnbits-client.ts   # LNbits REST wrapper
  │   ├── credits.ts         # Credit ledger (Redis or Postgres)
  │   └── pricing.ts         # BTC/USD rate + sat calculation
  ├── tests/
  ├── Dockerfile
  └── README.md
```

The main LlamaSketch API calls this service to:
- `POST /invoice` — Create a Lightning invoice for N credits
- `GET /credits/{token}` — Check remaining credits for a browser token
- `POST /debit/{token}` — Deduct 1 credit (called on generation completion)

---

## Web3 / Aqua Wallet (USDT on Liquid)

### Why Aqua / Liquid

- **Stablecoin** — USDT removes BTC price volatility. User pays $0.50, we receive ~$0.50.
- **Liquid Network** — Bitcoin sidechain, ~2 min confirmations, confidential transactions.
- **Aqua wallet** — Supports Lightning + Liquid + on-chain BTC in one app. Growing user base.
- **No KYC for user** — Wallet is self-custodial. User downloads app, loads USDT, pays.

### How it works

1. User selects "Pay with USDT" in top-up modal
2. We generate a Liquid address (or BIP21 URI with amount)
3. User scans QR in Aqua wallet (or any Liquid-compatible wallet: Green, SideSwap)
4. Liquid tx confirms in ~2 minutes (2 block confirmations)
5. Our backend watches for the tx, credits account on confirmation

### Implementation

- **Liquid node** — Run `elementsd` (Elements daemon) or use Blockstream's Esplora API for lightweight integration
- **Address generation** — HD wallet (BIP32) per user, or single address + memo for simpler setup
- **USDT detection** — Liquid USDT is an issued asset (asset ID: `ce091c998b83c78bb71a632313ba3760f1763d9cfcffae02258ffa9865a37bd2`). Monitor for transfers of this asset.
- **L-BTC also accepted** — Same Liquid address can receive L-BTC. Convert via SideSwap API if desired.

### Aqua-specific integration

Aqua supports [BIP21 payment URIs](https://github.com/nicbus/aqua-wallet) with Liquid:
```
liquidnetwork:ADDRESS?amount=0.50&assetid=USDT_ASSET_ID
```

Can also generate Lightning invoices as fallback — Aqua handles both protocols.

---

## Stripe (Fiat)

Already covered in `docs/production-roadmap.md` (Phase 3: P3.1–P3.5). Summary:

- Stripe Checkout for subscription tiers (Starter $8, Pro $20, Unlimited $40)
- Stripe Customer Portal for self-service billing management
- Webhook handler for `invoice.paid` / `subscription.deleted`
- Credit packs as one-time Stripe payments (alternative to subscription)

---

## Unified Payment UX

When user hits free tier limit:

```
┌──────────────────────────────────────┐
│  Top up to keep drawing              │
│                                      │
│  ┌──────────┐  ┌──────────┐         │
│  │ 50 gens  │  │ 200 gens │  ...    │
│  │  $0.50   │  │  $2.00   │         │
│  └──────────┘  └──────────┘         │
│                                      │
│  Pay with:                           │
│  [💳 Card]  [⚡ Lightning]  [🔗 USDT] │
│                                      │
│  Card → Stripe Checkout              │
│  Lightning → QR code (BOLT11)        │
│  USDT → QR code (Liquid address)     │
└──────────────────────────────────────┘
```

All rails credit the same account. Internal credit ledger is currency-agnostic — just tracks generation credits.

---

## Open Questions

1. **Volatility** — Do we price in sats (user takes BTC risk) or USD-pegged sats (we take BTC risk)? USD-pegged is better UX. USDT solves this for the Liquid rail.
2. **Refunds** — Lightning/Liquid payments are irreversible. If generation fails, credit back to account (not refund to wallet).
3. **Minimum invoice** — Lightning routing works poorly below ~10 sats. Minimum top-up should be ~1,000 sats ($0.50). Liquid has no practical minimum.
4. **Hold invoices** — Could use HODL invoices (pay first, settle on completion) but adds complexity. Simpler: pre-pay credits.
5. **Tax implications** — Receiving BTC/USDT is a taxable event in most jurisdictions. Need to track USD value at time of receipt.
6. **Liquid node vs API** — Running `elementsd` is ~2 GB disk + ~512 MB RAM. Alternative: use Blockstream Esplora/Greenlight API (lighter but custodial trust).
7. **Aqua wallet market share** — Aqua is relatively new. Should also support Green Wallet, SideSwap, and any generic Liquid wallet via standard BIP21 URIs.
8. **Auto-conversion** — Should we auto-convert received BTC/USDT to fiat (via Strike, Kraken, etc.) to avoid holding crypto? Reduces risk but adds complexity.
