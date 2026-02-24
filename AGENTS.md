# AGENTS.md

## Cursor Cloud specific instructions

### Architecture overview

LlamaSketch is a sketch-to-AI-image web app. Three tiers: vanilla HTML/JS frontend served by a Python FastAPI backend, which proxies generation requests to a remote ComfyUI GPU instance. See `CLAUDE.md` for full project notes.

### Running services

- **FastAPI backend (dev mode):** `mkdir -p data && PENCIL_CORS_ORIGINS="*" PENCIL_USAGE_SALT="dev-salt" uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`
  - Must run from the repo root (`/workspace`) so `static/` paths resolve.
  - The `data/` directory must exist before startup (SQLite usage DB is created there).
  - ComfyUI GPU backend will be unreachable — the app UI still loads and all non-generation endpoints work.

### Lint / Test / Typecheck

All commands per CI (`.github/workflows/ci.yml`):

| Check | Command (run from repo root) |
|---|---|
| ESLint | `npx eslint src/ tests/ --ignore-pattern node_modules` |
| Prettier | `npx prettier --check 'src/**/*.ts' 'tests/**/*.ts'` |
| TypeScript | `npx tsc --noEmit` |
| Vitest | `cd tests && npm test` |

### Gotchas

- Python packages install to `~/.local/` (user install). Add `$HOME/.local/bin` to `PATH` for `uvicorn` CLI.
- Node.js 22 is required (matches CI). The environment ships with nvm; `nvm use 22` or ensure system Node is v22.
- Root `npm ci` installs ESLint/Prettier/TypeScript; `tests/npm ci` installs Vitest + duplicated lint deps. Both are needed.
