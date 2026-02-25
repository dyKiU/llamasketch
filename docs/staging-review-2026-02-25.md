# Staging Review — 2026-02-25

Review of `origin/staging` after merge of `topic/dev-mode-and-daily-limit` and `topic/agentic-helpers`.

## Scope

Reviewed all staging-only changes (~1,093 lines added across 13 files), ran full CI checks (lint, typecheck, 73 tests), and manually tested the app in dev mode covering: preset loading, canvas drawing, sketch tips, AI assist (Suggest/Enhance), mock generation, variations, sessions, history, dark mode, and daily limit enforcement.

## Bugs Found

### 1. Dark mode header turns bright blue (FIXED)

**Severity**: High (visual)
**Files**: `static/index.html`, `static/landing.html`
**Root cause**: Header uses `background: var(--accent)`. In dark mode, `--accent` changes from `#1a1a2e` (dark navy) to `#6c7bff` (bright blue) for interactive elements, making the header glaringly bright — defeats the purpose of dark mode.
**Fix**: Added `--header-bg` CSS variable (`#1a1a2e` light, `#1e1e2e` dark), header uses `var(--header-bg)` instead of `var(--accent)`.
**Status**: Fixed in `index.html`. Landing page (`landing.html`) still has the same bug.

### 2. ESLint errors break CI (FIXED)

**Severity**: Medium (CI-blocking)
**File**: `tests/sketch-analysis.test.ts`
**Root cause**: `SketchTip` and `WHITE_THRESHOLD` imported but never used.
**Fix**: Removed unused imports.
**Status**: Fixed. All 73 tests pass, lint clean.

### 3. Landing page dark mode header (same as #1, unfixed)

**Severity**: Medium (visual)
**File**: `static/landing.html`
**Root cause**: Same `var(--accent)` header background issue — CSS variables in `landing.html` are a copy of `index.html` and weren't updated with the `--header-bg` fix.
**Status**: Not yet fixed (see suggested actions below).

### 4. Sketch tips use innerHTML with template literals

**Severity**: Low (XSS hardening)
**File**: `static/index.html` line ~2383
**Detail**: `updateSketchTips()` builds HTML via template literal and sets `container.innerHTML`. The tip data (`t.id`, `t.message`) comes from client-side `saGenerateTips()` with hardcoded strings, so this isn't exploitable today. However, it's inconsistent with the XSS fix in commit `3b7e5d6` which converted `setSuggestionChips` from innerHTML to `createElement`/`textContent`.
**Status**: Not fixed (low priority).

### 5. Duplicate CSS theme variables across files

**Severity**: Low (maintainability)
**Files**: `static/index.html`, `static/landing.html`
**Detail**: Both files contain identical copies of the `:root` / `body.dark` CSS variable blocks. Changes to one (like the `--header-bg` fix) must be manually replicated to the other. This caused bug #3.
**Status**: Architectural debt, not a bug per se.

## What's Working Well

- **Dev mode (P0)**: MockComfyUIClient produces gradient/checkerboard images with "DEV MODE" badge. Health check reports connected, GPU stats show simulated 24GB. Full frontend+backend development cycle works without a GPU.
- **Daily free limit (P1.6)**: Backend enforces `PENCIL_DAILY_FREE_LIMIT` via 429. Frontend shows X/20 counter with green/orange/red color progression. Toast message on limit hit.
- **Sketch analysis (Layer 1)**: Client-side canvas analysis runs on every stroke pause (~2ms). Tips for off-center, low-coverage, sparse density appear correctly and are dismissible with persistence via localStorage.
- **AI assist (Layers 2+3)**: Suggest (vision) and Enhance (prompt) buttons work in dev mode with mock responses. Suggestion chips are clickable and apply to prompt. XSS fix properly uses createElement/textContent.
- **Existing features**: Presets, canvas drawing, undo/redo, variations, sessions, history, lightbox, dark mode toggle, settings layouts — all functional.

## Suggested Actions

### High Priority

1. **Fix landing page dark mode header** — Apply the same `--header-bg` variable fix from `index.html` to `landing.html`. One-line CSS change.

2. **Extract shared CSS variables to a common file** — The duplicated `:root`/`body.dark` blocks between `index.html` and `landing.html` will keep causing drift bugs. Extract to `static/css/theme.css` and `<link>` it from both pages.

3. **Add `checkAssistConfig` to the health poll cycle** — Currently `checkAssistConfig()` runs once at page load. If the backend restarts with a different `PENCIL_ANTHROPIC_API_KEY` config, the Suggest/Enhance buttons won't appear/disappear until a full page reload. Could piggyback on the existing 30-second `checkHealth` interval.

### Medium Priority

4. **Harden remaining innerHTML usages** — The XSS fix for suggestion chips (commit `3b7e5d6`) was good but incomplete. `updateSketchTips()` still uses innerHTML with template literals. While safe today (data is client-side), applying the same createElement pattern would be consistent and future-proof if tips ever come from an API.

5. **Add backend tests** — The backend has zero Python tests. Key targets: `MockComfyUIClient` image generation, daily limit enforcement logic in the generate endpoint, `UsageTracker` CRUD operations, and the assist mock responses. pytest + httpx's `AsyncClient` for FastAPI testing.

6. **Rate limiting on assist endpoints is shared with generation** — `/api/assist/vision` and `/api/assist/prompt` share the same `_check_rate_limit` pool as `/api/generate`. A user who hits rate limit from rapid drawing (live mode) will also be blocked from clicking Suggest/Enhance. Consider a separate rate limit bucket for assist calls.

### Low Priority

7. **`creativityRange` localStorage parse not guarded** — Line ~2887: `JSON.parse(savedRange)` — if `savedRange` is corrupted/invalid JSON, this will throw and break init. The `dismissedTips` parse was already wrapped in try-catch (commit `3b7e5d6`), but this one was missed.

8. **Sessions modal accessibility** — The sessions modal doesn't trap focus or respond to Escape key consistently. Minor UX polish.

9. **Consider `anthropic` dependency size** — `anthropic>=0.49` adds ~5MB to the Docker image. In production without an API key, `assist.py` still imports the module at startup. Could lazy-import only when `is_enabled()` returns true and the key is set.
