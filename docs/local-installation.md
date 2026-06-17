# Local Installation

SkillForge is local-first. There is no cloud account, no telemetry, and no auth. This page covers all the ways to run it locally.

## TL;DR — one command, one port

```bash
cd apps/api  && pip install -e ".[dev]"
cd ../cli    && pip install -e .
skillforge serve --build-web     # builds the Web UI once, then serves everything on :8000
```

Open <http://localhost:8000>. The API and the Web UI share that single port — one process, no CORS, no Node runtime left running. This is the recommended everyday flow.

## Single executable (no Python/Node on the target)

```bash
pip install pyinstaller
./scripts/build-binary.sh        # produces dist/skillforge (~22 MB, one file)
./dist/skillforge                # serves http://localhost:8000
```

The binary bundles the Python runtime, the API, the tool catalog, the templates, and the pre-built Web UI export. It runs with zero dependencies on the target machine (verified with `PATH=/usr/bin:/bin`). Running it with no args defaults to `serve`. The binary is platform-specific — rebuild per OS. See `scripts/skillforge.spec` for what's bundled.

## Run modes (`skillforge serve`)

| Mode | Command | What runs | Ports |
|------|---------|-----------|-------|
| **Bundled** (default) | `skillforge serve` | API + pre-built Web UI in one process | one (`:8000`) |
| Build then bundle | `skillforge serve --build-web` | rebuild Web UI, then bundle | one (`:8000`) |
| **Dev** (hot-reload) | `skillforge serve --dev` | API + Next.js dev server | `:8000` + `:3000` |
| **API-only** | `skillforge serve --api-only` | headless API | one (`:8000`) |

In bundled mode the Web UI is a static Next.js export served by FastAPI, so the browser's relative URLs (`/api/*`, `/health`) hit the API directly. In dev mode the Next dev server proxies those paths to the API.

### Where the bundled Web UI comes from

`skillforge serve` looks for the static export in this order:

1. `$SKILLFORGE_WEB_DIR` (explicit override; the Docker image sets this to `/opt/skillforge/web`).
2. `apps/web/out` relative to the repo root (auto-detected from the package location).
3. `apps/web/out` relative to the current working directory.

If none exists, it either builds it (`--build-web`) or falls back to API-only mode with a hint.

## Docker

**Single container (recommended)** — API + Web UI on one port:

```bash
cp .env.example .env
docker compose --profile single up --build
# → http://localhost:8000
```

The multi-stage `apps/api/Dockerfile` builds the Web UI export and bakes it into the image, so the resulting container is fully self-contained.

**Two services** — separate containers/ports (useful for UI-focused development):

```bash
docker compose up --build
# → API http://localhost:8000, Web UI http://localhost:3000
```

Installed skills persist in the `skillforge-data` volume, mounted at `/data/skills`.

## Run the apps directly

### Backend (FastAPI)

```bash
cd apps/api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn skillforge_api.main:app --reload --port 8000
```

OpenAPI docs: <http://localhost:8000/docs>.

### Web UI (Next.js)

```bash
cd apps/web
npm install
npm run dev      # http://localhost:3000 (dev)
npm run build    # produces out/ — what `skillforge serve` serves in bundled mode
```

### CLI

```bash
cd apps/cli
pip install -e .        # installs into the same venv as the API
skillforge --help
```

The CLI reuses the API's service layer, so install it into the same virtualenv (or `pip install -e ../api` first).

## Where skills are installed

```
~/.skillforge/skills/<skill-name>/
  SKILL.md
  README.md
  config.yaml
  prompts/
  templates/
  scripts/
  examples/
```

Override with `SKILLFORGE_SKILLS_DIR`.

## Configuration

All config comes from environment variables (see [`.env.example`](../.env.example)). The defaults let everything run offline:

| Variable                      | Default                         | Purpose                         |
| ----------------------------- | ------------------------------- | ------------------------------- |
| `SKILLFORGE_AI_PROVIDER`      | `mock`                          | `mock` \| `openai-compatible` \| `ollama-local` |
| `SKILLFORGE_OPENAI_BASE_URL`  | `https://api.openai.com/v1`     | OpenAI-compatible endpoint      |
| `SKILLFORGE_OPENAI_API_KEY`   | _(empty)_                       | Required for `openai-compatible`|
| `SKILLFORGE_OLLAMA_BASE_URL`  | `http://localhost:11434`        | Ollama daemon                   |
| `SKILLFORGE_MODEL`            | `gpt-4.1`                       | Model name                      |
| `SKILLFORGE_SKILLS_DIR`       | `~/.skillforge/skills`          | Install directory               |
| `SKILLFORGE_API_HOST`         | `0.0.0.0`                       | API bind host                   |
| `SKILLFORGE_API_PORT`         | `8000`                          | API bind port                   |
| `SKILLFORGE_DB_PATH`          | `skillforge.db`                 | SQLite registry path            |
| `SKILLFORGE_WEB_API_URL`      | `http://localhost:8000`         | Where the Web UI proxies to (dev mode) |
| `SKILLFORGE_WEB_DIR`          | _(auto-detected)_               | Path to the static Web UI export (`apps/web/out`); used by bundled mode |

## Using a local LLM (Ollama)

```bash
# 1. Pull a model
ollama pull llama3.1

# 2. Configure SkillForge
export SKILLFORGE_AI_PROVIDER=ollama-local
export SKILLFORGE_MODEL=llama3.1

# 3. Run
skillforge plan "I need a backend skill for FastAPI and PostgreSQL"
```

## Using an OpenAI-compatible provider

```bash
export SKILLFORGE_AI_PROVIDER=openai-compatible
export SKILLFORGE_OPENAI_BASE_URL=https://api.openai.com/v1   # or OpenRouter/Groq/Together/vLLM
export SKILLFORGE_OPENAI_API_KEY=sk-...
export SKILLFORGE_MODEL=gpt-4.1
```

## Testing

```bash
cd apps/api && pytest -q
```

Tests use the mock provider and an isolated temp DB + skills dir, so they run fully offline.
