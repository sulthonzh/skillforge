# SkillForge CLI

Command-line interface for SkillForge.

```bash
pip install -e .
skillforge --help
```

## Commands

```bash
skillforge serve                                   # start the API server
skillforge plan "I need a backend skill for FastAPI and PostgreSQL"
skillforge generate --manifest ./config.yaml --out ./generated-skill
skillforge install ./generated-skill [--overwrite]
skillforge list                                    # list installed skills
skillforge validate ./generated-skill              # validate a skill folder
skillforge remove backend-fastapi-postgres         # remove an installed skill
```

## Configuration

The CLI reads the same environment variables as the API (see the root
[`.env.example`](../../.env.example)). The default AI provider is `mock`, so
`skillforge plan` works fully offline.

## How it fits together

The CLI is a thin Typer wrapper around the same service layer the FastAPI app
uses (`skillforge_api.services.*`). `skillforge serve` launches uvicorn; the
other commands run services directly so you can build skills without a server.
