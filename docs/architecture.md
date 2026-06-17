# Architecture

SkillForge is a local-first monorepo with three apps that share a single Python service layer.

```
┌──────────────────────────────────────────────────────────────────┐
│  apps/web   (Next.js + TS + Tailwind)   :3000                    │
│  ChatPanel → ManifestEditor → SkillPreview → InstallButton       │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP (proxied via next.config rewrites)
┌────────────────────────────▼─────────────────────────────────────┐
│  apps/api   (FastAPI)                       :8000                │
│  routers/  ──►  services/  ──►  repositories/                     │
│  (health, chat,    (planner, generator,     (SQLite registry)    │
│   skills,           installer, validator,                        │
│   registry,         template_renderer,                           │
│   templates)        tool_catalog, ai_provider)                   │
└────────────────────────────┬─────────────────────────────────────┘
                             │ reuses the same service layer
┌────────────────────────────▼─────────────────────────────────────┐
│  apps/cli   (Typer + Rich)                                       │
│  serve | plan | generate | install | list | validate | remove    │
└──────────────────────────────────────────────────────────────────┘
                             │ writes
                  ┌──────────▼──────────┐
                  │ ~/.skillforge/skills│  ← filesystem (source of truth)
                  └─────────────────────┘
```

## Layering

1. **Routers** (`skillforge_api/routers/`) — thin HTTP adapters. Validate request shape, call a service, return a schema. No business logic.
2. **Services** (`skillforge_api/services/`) — all business logic. Pure where possible:
   - `tool_catalog` — loads & matches the editable YAML catalog.
   - `ai_provider` — provider-agnostic LLM abstraction (mock / openai-compatible / ollama).
   - `ai_skill_planner` — turns natural language into a `SkillManifest`.
   - `template_renderer` + `skill_generator` — render `SKILL.md`/`README.md` via Jinja2 and `config.yaml` via PyYAML.
   - `skill_validator` — enforces the skill contract.
   - `skill_installer` — writes files into `~/.skillforge/skills`.
   - `skill_registry` — facade over the repository for list/get/validate/remove.
3. **Repositories** (`skillforge_api/repositories/`) — persistence. The SQLite registry is a *fast index*; the filesystem is the source of truth for installed skill contents.
4. **Schemas** (`skillforge_api/schemas/`) — Pydantic models shared by routers, the CLI, and tests.

## Why the CLI and API share services

Both `apps/api` and `apps/cli` import `skillforge_api.services.*`. This guarantees identical behavior between the Web UI and the command line: `skillforge plan` and `POST /api/chat/plan-skill` run the exact same code path.

## Bundled mode — one process, one port

`skillforge serve` (default) serves both the API and the Web UI from a single
FastAPI process on a single port. The Web UI is a static Next.js export
(`apps/web/out`) mounted by `create_app(static_dir=...)`. The browser loads the
UI from the same origin as the API, so relative URLs (`/api/*`, `/health`)
resolve with no proxy and no CORS. This is what gives SkillForge its "single
binary" feel without freezing a Python+Node bundle.

```
                ┌─────────────────────────────────────────┐
   browser ───► │  FastAPI :8000                          │
                │  ├── /health, /api/*      → API routers  │
                │  └── /* (catch-all)       → StaticFiles  │
                │                              (apps/web/out) │
                └─────────────────────────────────────────┘
```

In `--dev` mode the Next.js dev server runs on `:3000` alongside the API on
`:8000` and proxies `/api/*` to it, giving contributors hot-reload.

## Safety boundaries

- The generator and installer are **pure** w.r.t. execution: they never call `subprocess` or `os.system`. Generated `scripts/` files are reference text on disk.
- Install requires an explicit user action (API call with `overwrite` flag, or CLI `--yes`). The installer refuses to overwrite without `overwrite=True` and returns a 409 from the API instead.
- Secrets are read only from environment variables (`settings.py`) and never logged.

## Data flow: planning a skill

```
user message
   │
   ▼
AISkillPlanner.plan()
   │  ┌─ mock  → deterministic manifest from catalog heuristics
   │  └─ llm   → provider.complete_json() → parsed into SkillManifest
   ▼
SkillManifest  ──►  (edited in UI / CLI)  ──►  SkillGenerator.generate()
                                                      │
                                                      ▼
                          [SKILL.md, README.md, config.yaml, prompts/, templates/, ...]
                                                      │
                                          SkillValidator.validate_manifest()
                                                      │ valid?
                                          SkillInstaller.install()  ──►  ~/.skillforge/skills/<name>
                                                                      └─►  RegistryRepository.upsert()
```
