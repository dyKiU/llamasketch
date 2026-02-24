# AGENTS.md

## Cursor Cloud specific instructions

### Architecture overview

LlamaSketch is a sketch-to-AI-image web app. See `CLAUDE.md` for full project notes.

- **Backend**: Python 3.12 FastAPI app in `backend/` — run with `uvicorn backend.main:app --reload` from repo root
- **Frontend**: Vanilla HTML/JS in `static/` (no build step) — served by FastAPI at `/` and `/app`
- **TypeScript modules**: Pure logic in `src/` with Vitest tests in `tests/`
- **External dependency**: ComfyUI on a GPU instance (not available in Cloud VM — backend gracefully reports it as unreachable)

### Running services

**FastAPI backend (dev mode):**
```bash
mkdir -p data
export PENCIL_CORS_ORIGINS="*"
export PENCIL_USAGE_SALT="dev-salt"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- `mkdir -p data` is required — the SQLite usage tracker needs the `data/` directory to exist
- `PENCIL_CORS_ORIGINS="*"` is needed for local dev (default restricts to production domains)
- ComfyUI will be unreachable — the `/api/health` endpoint reports this gracefully; generation jobs will fail with "All connection attempts failed"
- `uvicorn` is installed to `~/.local/bin` — make sure `PATH` includes it (the update script handles this)

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
