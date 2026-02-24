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

### Running the backend locally (optional)

Only needed if working on backend Python code:
```bash
mkdir -p data
export PENCIL_CORS_ORIGINS="*"
export PENCIL_USAGE_SALT="dev-salt"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- `mkdir -p data` is required — the SQLite usage tracker needs the `data/` directory to exist
- `PENCIL_CORS_ORIGINS="*"` is needed for local dev (default restricts to production domains)
- ComfyUI will be unreachable — generation jobs will fail gracefully
- `uvicorn` is installed to `~/.local/bin` — make sure `PATH` includes it

### Lint / typecheck / test commands

All match CI (see `.github/workflows/ci.yml`):
- **ESLint**: `npm run lint`
- **Prettier**: `npm run format:check`
- **TypeScript**: `npm run typecheck`
- **Vitest tests**: `cd tests && npm test` (or `npm run test` from root)

### Gotchas

- Python packages install to `~/.local/` (user install) — `uvicorn` and `fastapi` CLI are at `~/.local/bin/`
- The `data/` directory is `.gitignore`d and must be created before starting the backend
- `tests/` has its own `package.json` and `node_modules` — always run `npm ci` in both root and `tests/`
