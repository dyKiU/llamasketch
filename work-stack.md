# Work Stack

## Variations Bulk Dropdown

After all 16 variations have been rendered, show a dropdown/button allowing the user to generate up to 128 additional variations in a single batch.

### Milestones

- [x] **M1: Extract `src/variety-batch.ts`** — Pure batch scheduler with no DOM/fetch deps. Functions: `createBatch`, `fireJobs`, `completeJob`, `failJob`, `abortBatch`, plus completion/progress hooks.
- [x] **M2: Tests `tests/variety-batch.test.ts`** — 11 tests covering: fire N jobs, abort cancels pending, stale generation ignored, completion callback fires, progress counts, batch extension.
- [x] **M3: Wire `variety-batch.ts` into `index.html`** — Inlined sync copy (matching queue-manager pattern). Variety batch manager delegates pure state to vb* functions.
- [x] **M4: "Generate More" dropdown UI** — `[+ More ▾]` dropdown in variations header with 16/32/64/128 options. Fires additional jobs appended to existing strip.
- [x] **M5: Progress + guard rails** — Spinner shows `Generating... N/M` across all batches. Dropdown disabled while bulk batch is in-flight. New strokes abort everything.
