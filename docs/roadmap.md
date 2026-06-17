# Roadmap

SkillForge v1 is a focused, local-first MVP. This roadmap lists what shipped, what's planned, and what is intentionally out of scope.

## Status: v1 MVP ✅

Shipped:

- [x] Local Web UI (Next.js + TS + Tailwind + shadcn-style components)
- [x] Local backend API (FastAPI)
- [x] Chat-based AI skill planning
- [x] AI tool recommendation with reasons
- [x] Editable manifest (cards + raw JSON)
- [x] Live file preview (SKILL.md, README.md, config.yaml, prompts/, templates/, …)
- [x] Local installation into `~/.skillforge/skills`
- [x] Installed-skill registry (list, inspect, validate, remove)
- [x] CLI (`serve`, `plan`, `generate`, `install`, `list`, `validate`, `remove`)
- [x] Provider-agnostic AI (mock / openai-compatible / ollama-local)
- [x] Validation (kebab-case names, ≥2 tools, required sections, etc.)
- [x] Example skills (`backend-fastapi-postgres`, `data-airflow-dbt-bigquery`, `ai-rag-langchain-pgvector`)
- [x] Unit + API tests (planner, generator, installer, validator, registry, catalog)
- [x] Docker Compose stack
- [x] **One-command run** — `skillforge serve` serves API + Web UI from a single port (no separate Node process)
- [x] **Single-binary distribution** — `./scripts/build-binary.sh` produces a standalone PyInstaller executable (API + embedded Web UI export, no Python/Node install on the target)
- [x] OSS docs (architecture, manifest spec, planner, catalog, install, roadmap)

## Planned (v1.x)

- [ ] **Cross-platform binary releases** — CI (GitHub Actions) that builds macOS, Linux, and Windows binaries on tag push and publishes them to GitHub Releases. The single-binary build itself already ships; this is purely release automation.
- [ ] **Skill template marketplace** — community sharing of skill templates (read-only registry, no cloud backend required).
- [ ] **Skill versioning & upgrade** — diff/upgrade flow when a skill is regenerated.
- [ ] **Per-skill test harness generation** — emit runnable pytest/playwright scaffolds tailored to the skill's stack.
- [ ] **Pluggable output formats** — emit MDX or JSON in addition to markdown.
- [ ] **Streaming plan responses** — Server-Sent Events for the chat panel.
- [ ] **Multi-language catalog contributions** — a PR template + CI check for catalog edits.
- [ ] **Offline LLM model picker** — detect installed Ollama models and offer them in the UI.

## Considered but not committed (v2+)

- [ ] Team sharing via a shared skills directory (still local, no cloud).
- [ ] Skill dependency graph (one skill composing another).
- [ ] A "skill linter" CI action usable in external repos.

## Out of scope (by design)

These will **not** be built, to keep SkillForge local-first, simple, and safe:

- Cloud sync of generated skills.
- Multi-user workspaces.
- Authentication and authorization.
- Team permission systems.
- Remote/hosted deployment as a managed service.
- Auto-executing generated scripts.
- A complex plugin runtime.
- Enterprise dashboard / billing.

If any of these matter to you, SkillForge's permissive MIT license and clean service layer make it straightforward to fork.
