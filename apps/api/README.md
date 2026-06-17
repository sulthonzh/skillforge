# SkillForge API

The FastAPI backend for SkillForge. Local-first, no auth, no cloud.

## Run

```bash
pip install -e ".[dev]"
uvicorn skillforge_api.main:app --reload --port 8000
```

- Health: <http://localhost:8000/health>
- OpenAPI docs: <http://localhost:8000/docs>

## Environment

See the root [`.env.example`](../../.env.example). The default AI provider is `mock`, so the API runs fully offline with zero configuration.

## Layout

```
skillforge_api/
  main.py              FastAPI app + router wiring
  settings.py          pydantic-settings configuration
  database.py          SQLite + SQLModel engine
  routers/             HTTP endpoints (health, chat, skills, registry, templates)
  schemas/             Pydantic request/response models
  services/            Business logic (planner, generator, installer, ...)
  repositories/        Persistence (registry repository)
  templates/           Jinja2 templates for generated skill files
  data/                tool_catalog.yaml
```

See [`docs/architecture.md`](../../docs/architecture.md) for the full design.
