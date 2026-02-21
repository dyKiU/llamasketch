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
