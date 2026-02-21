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
