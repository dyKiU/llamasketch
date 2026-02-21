# Work Stack

## Variations Bulk Dropdown

After all 16 variations have been rendered, show a dropdown/button allowing the user to generate up to 128 additional variations in a single batch.

### Milestones

- [x] **M1: Extract `src/variety-batch.ts`** — Pure batch scheduler with no DOM/fetch deps. Functions: `createBatch`, `fireJobs`, `completeJob`, `failJob`, `abortBatch`, plus completion/progress hooks.
- [x] **M2: Tests `tests/variety-batch.test.ts`** — 11 tests covering: fire N jobs, abort cancels pending, stale generation ignored, completion callback fires, progress counts, batch extension.
- [x] **M3: Wire `variety-batch.ts` into `index.html`** — Inlined sync copy (matching queue-manager pattern). Variety batch manager delegates pure state to vb* functions.
- [x] **M4: "Generate More" dropdown UI** — `[+ More ▾]` dropdown in variations header with 16/32/64/128 options. Fires additional jobs appended to existing strip.
- [x] **M5: Progress + guard rails** — Spinner shows `Generating... N/M` across all batches. Dropdown disabled while bulk batch is in-flight. New strokes abort everything.

---

## Canvas Anchor/Lock Region

Allow the user to select an area of the canvas to be "anchored" — that region stays untouched during generation (inpainting mask). Strokes and creativity only affect the non-anchored area.

- Selection tool (rectangle or lasso) to define the anchored region
- Visual indicator (hatching, tint, or border) showing which area is locked
- Send the anchor mask alongside the sketch to the API so the model preserves those pixels
- Toggle to clear/reset the anchor
- Should compose with existing drawing tools (pencil/eraser work only outside the anchor, or optionally inside too)

---

## Settings Drawer

Right-side slide-in drawer (320px), triggered by the existing gear icon. Provides centralized control over canvas, generation, and output settings.

### Sections

- **Canvas**: Size (512/768/1024), fit mode, layout mode (side-by-side / stacked)
- **Generation**: Steps, CFG, denoise strength
- **Output**: Upscale toggle, auto-variations count, idle delay

Esc or click-outside to close. Canvas stays visible while drawer is open.

### Milestones

- [ ] **M1: Drawer skeleton** — Slide-in panel, open/close animation, gear icon wiring, click-outside dismiss
- [ ] **M2: Canvas section** — Size picker, fit mode toggle, layout mode toggle. Wire to existing canvas resize logic
- [ ] **M3: Generation section** — Steps slider, CFG slider, denoise slider. Wire to generate request params
- [ ] **M4: Output section** — Upscale toggle (pairs with upscale feature), auto-variations count, idle delay slider
- [ ] **M5: Persist to localStorage** — Save all settings, restore on page load, reset-to-defaults button

---

## Post-Generation Upscale Button

"2x Upscale" button on output preview after generation completes. Uses server-side Real-ESRGAN via ComfyUI.

- **Model**: `RealESRGAN_x2plus.pth` (~67 MB), loaded into ComfyUI models dir
- **Endpoint**: Synchronous `POST /api/upscale/{job_id}` — returns upscaled PNG directly (~1-2s)
- **Frontend**: Button shows idle / loading spinner / done states on the output preview
- **History**: Save both original + upscaled to IndexedDB session history
- **Auto-upscale**: Optional toggle in settings drawer to upscale every generation automatically

### Milestones

- [ ] **M1: ComfyUI workflow + model download** — Add `RealESRGAN_x2plus.pth` to setup script, create upscale workflow JSON
- [ ] **M2: Backend endpoint** — `POST /api/upscale/{job_id}` sends original image through upscale workflow, returns result
- [ ] **M3: Frontend button** — "2x Upscale" button on output preview with idle/loading/done states
- [ ] **M4: History integration** — Store upscaled variant alongside original in IndexedDB, show badge in history strip
- [ ] **M5: Auto-upscale toggle** — Settings drawer toggle that automatically upscales every completed generation

---

## User Database + Security Audit

User accounts, auth, and quota tracking. Currently no database — jobs are in-memory and lost on restart.

### Database choice: Supabase

Supabase over raw Postgres for faster iteration: built-in auth (email + OAuth), row-level security, JS client SDK, hosted dashboard, and a generous free tier. Avoids building auth from scratch. Can migrate to self-hosted Postgres later if needed.

### Schema (initial)

- `auth.users` — Supabase built-in (email, OAuth, JWT)
- `public.profiles(id, user_id, plan, credits_remaining, created_at)` — linked to auth.users
- `public.generations(id, user_id, prompt, created_at, r2_key)` — generation log for quota + history

### Security audit checklist

- [ ] **Auth flows**: Email verification required, OAuth state validation, JWT expiry + refresh
- [ ] **Row-level security (RLS)**: Users can only read/write their own rows — no cross-user data leaks
- [ ] **API auth middleware**: Every `/api/generate` call validates JWT. Reject unauthenticated (except free tier via IP/fingerprint)
- [ ] **Rate limiting**: Per-user and per-IP. Prevent abuse of free tier (IP rotation, throwaway emails)
- [ ] **Input validation**: Prompt length limits, image size limits (already have `max_image_size`), sanitize all user input
- [ ] **CORS policy**: Tighten from `allow_origins=["*"]` to actual domains only
- [ ] **SQL injection**: Supabase client uses parameterized queries — verify no raw SQL anywhere
- [ ] **Secrets management**: No credentials in code or repo. `.env` files on server only, `~/secrets/` locally
- [ ] **HTTPS enforcement**: All traffic over TLS, HSTS header, no mixed content
- [ ] **Dependency audit**: `pip audit` + `npm audit` in CI pipeline
- [ ] **CSP headers**: Add Content-Security-Policy to nginx configs

### Milestones

- [ ] **M1: Supabase project setup** — Create project, enable email + Google OAuth, set redirect URLs for staging/prod
- [ ] **M2: Database schema + RLS** — Create `profiles` and `generations` tables with row-level security policies
- [ ] **M3: Backend auth middleware** — Validate Supabase JWT on API endpoints, extract user_id, enforce quotas
- [ ] **M4: Frontend auth UI** — Login/signup modal, session persistence, show user state in header
- [ ] **M5: Security audit pass** — Run through checklist above, tighten CORS, add CSP, run dependency audits

---

## Client-Side Image Encryption (Low Priority)

Users hold their own keys — generated images are encrypted before storage so neither the server nor anyone without the key can view them.

- Encrypt images client-side (Web Crypto API, AES-256-GCM) before uploading to R2/S3
- Key derived from user passphrase (PBKDF2) or stored in browser (localStorage / IndexedDB)
- Server only ever sees ciphertext — zero-knowledge image storage
- Decrypt on download/display in browser
- Key export/backup flow so users don't lose access (QR code, mnemonic, file download)
- Optional: share encrypted images with other users via public-key exchange
- Pairs well with Web3 wallet integration — wallet keys could derive encryption keys
- **Trade-off**: Server can't generate thumbnails, do NSFW filtering, or serve gallery from encrypted images. May need two tiers: "private encrypted" vs "public gallery"
