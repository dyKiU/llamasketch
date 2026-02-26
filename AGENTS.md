# AGENTS.md

## Cursor Cloud specific instructions

### Architecture overview

LlamaSketch is a sketch-to-AI-image web app. See `CLAUDE.md` for full project notes.

- **Frontend**: Vanilla HTML/JS in `static/` (no build step) — the primary development target
- **TypeScript modules**: Pure logic in `src/` with Vitest tests in `tests/`
- **Backend**: Python 3.12 FastAPI app in `backend/` — usually not needed locally; staging is auto-deployed
- **External dependency**: ComfyUI on a GPU instance (not available in Cloud VM)

### Development scope

**Frontend-only mode**: The GPU backend is not running, so focus on frontend work (HTML/JS in `static/`, TypeScript in `src/`, tests in `tests/`). The backend is not needed for most development tasks.

**Staging site**: `https://staging.llamasketch.com` — auto-deployed via GitHub Actions on push to `staging` branch. Use this to verify deployed frontend changes in a browser.

### Running the backend locally

**Dev mode** (recommended — no GPU required):
```bash
mkdir -p data
PENCIL_DEV_MODE=true PENCIL_CORS_ORIGINS="*" PENCIL_USAGE_SALT="dev-salt" \
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Dev mode uses `MockComfyUIClient` which returns synthetic gradient/checkerboard images with a "DEV MODE" badge. Health check reports connected, GPU stats show a simulated 24GB GPU. Fully functional for end-to-end frontend+backend development.

**Without dev mode** (real ComfyUI required):
```bash
mkdir -p data
PENCIL_CORS_ORIGINS="*" PENCIL_USAGE_SALT="dev-salt" \
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- `mkdir -p data` is required — the SQLite usage tracker needs the `data/` directory to exist
- `PENCIL_CORS_ORIGINS="*"` is needed for local dev (default restricts to production domains)
- `uvicorn` is installed to `~/.local/bin` — make sure `PATH` includes it

### CI / GitHub Actions

Two workflows run on push to `staging` (and `master`/`main`):

1. **CI** (`.github/workflows/ci.yml`) — lint + typecheck + test
2. **Deploy Staging** (`.github/workflows/deploy-staging.yml`) — same checks, then SSH deploy to `staging.llamasketch.com`

**CI pipeline steps** (must all pass before deploy):
1. ESLint: `npx eslint src/ tests/ --ignore-pattern node_modules`
2. Prettier: `npx prettier --check 'src/**/*.ts' 'tests/**/*.ts'`
3. TypeScript: `npx tsc --noEmit`
4. Vitest: `cd tests && npm test`

**Deploy** (staging only): SSH → `git pull` → `docker compose build` → `docker compose up -d` → health check → config verify.

### Lint / typecheck / test commands

All match CI (see `.github/workflows/ci.yml`):
- **ESLint**: `npm run lint`
- **Prettier check**: `npm run format:check`
- **Prettier fix**: `npx prettier --write 'src/**/*.ts' 'tests/**/*.ts'`
- **TypeScript**: `npm run typecheck`
- **Vitest (frontend)**: `cd tests && npm test` (or `npm run test` from root)
- **Pytest (backend)**: `.venv/bin/python -m pytest backend/tests/ -v`

### Testing — TDD workflow

TDD is mandatory for all unit-testable components:
1. Write tests first in `tests/*.test.ts` that import from `src/*.ts`
2. Run tests — confirm they **fail** (RED)
3. Write the implementation in `src/*.ts`
4. Run tests — confirm they **pass** (GREEN)
5. Sync the inline copy into `static/index.html` (matching the queue-manager pattern)
6. **Run Prettier** before committing: `npx prettier --write 'src/**/*.ts' 'tests/**/*.ts'`
7. Git commit

**Module pattern**: Extract pure logic from `index.html` into `src/*.ts` with no DOM dependencies. Types + pure functions that take data in and return data out. DOM interaction stays in `index.html`.

**Existing modules** (follow the same pattern):
- `src/queue-manager.ts` → `tests/queue-manager.test.ts`
- `src/canvas-tools.ts` → `tests/canvas-tools.test.ts`
- `src/variety-batch.ts` → `tests/variety-batch.test.ts`
- `src/creativity.ts` → `tests/creativity.test.ts`
- `src/format-utils.ts` → `tests/format-utils.test.ts`
- `src/image-layout.ts` → `tests/image-layout.test.ts`
- `src/sketch-analysis.ts` → `tests/sketch-analysis.test.ts`

**Backend tests** (28 tests in `backend/tests/`):
- `test_api.py` — API endpoint integration tests (dev mode)
- `test_assist.py` — AI assist module (mock responses)
- `test_mock_comfyui.py` — Mock ComfyUI client
- `test_usage.py` — Usage tracking + IP hashing

### QA checklist before pushing

1. `npx prettier --write 'src/**/*.ts' 'tests/**/*.ts'` — **Prettier MUST pass or CI fails**
2. `npm run lint` — ESLint
3. `npx tsc --noEmit` — TypeScript type-check
4. `cd tests && npm test` — all Vitest tests pass
5. `.venv/bin/python -m pytest backend/tests/ -v` — all Python tests pass
6. `python3 -c "import ast; ast.parse(open('backend/<file>.py').read())"` — syntax check any changed Python files

### Branching strategy

- **`master`** — production branch, deploys to `llamasketch.com`
- **`staging`** — staging branch, auto-deploys to `staging.llamasketch.com`
- **`topic/*`** — feature branches, merged into `master` or `staging`
- Feature work happens on `master` (or feature branches merged into `master`)
- When ready to test: merge `master` → `staging` and push
- Never push untested changes directly to `staging` — always flow through `master` first

### Gotchas

- **Prettier is enforced in CI** — always run `npx prettier --write` on `.ts` files before committing
- Python packages install to `~/.local/` (user install) — `uvicorn` and `fastapi` CLI are at `~/.local/bin/`
- The `data/` directory is `.gitignore`d and must be created before starting the backend
- `tests/` has its own `package.json` and `node_modules` — always run `npm ci` in both root and `tests/`
- Inline JS copies in `static/index.html` must be manually synced with `src/*.ts` modules — no bundler
