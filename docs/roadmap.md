# Roadmap

SkillForge is a local-first, open-source AI-powered engineering skill builder.
Describe an engineering need in plain text, get back a focused, installable
skill (SKILL.md, README, config.yaml + runnable scaffolds) for AI coding tools.

This roadmap tracks what shipped, what's planned, and what is intentionally out
of scope. Status as of v1.x.

---

## Status: v1.x — feature-complete MVP ✅

### Core builder
- [x] Local Web UI (Next.js 14 + TS + Tailwind + shadcn-style components)
- [x] Local backend API (FastAPI)
- [x] Chat-based AI skill planning (mock planner + LLM planner)
- [x] AI tool recommendation with reasons
- [x] Editable manifest (cards + raw JSON)
- [x] Live file preview (SKILL.md, README.md, config.yaml, prompts/, templates/, scripts/)
- [x] Local installation into `~/.skillforge/skills`
- [x] Installed-skill registry (list, inspect, validate, remove)
- [x] CLI (`serve`, `plan`, `generate`, `install`, `list`, `validate`, `remove`)
- [x] Validation (kebab-case names, ≥2 tools, required sections, etc.)
- [x] Example skills (`backend-fastapi-postgresql`, `data-airflow-dbt-bigquery`, `ai-rag-langchain-pgvector`)

### Distribution & operation
- [x] **One-command run** — `skillforge serve` serves API + Web UI from a single port
- [x] **Single-binary distribution** — PyInstaller onefile (API + embedded Web UI export, no Python/Node on target). Build guarded against the `jaraco.text` crash and size bloat (22 MB, fails fast on regression).
- [x] **Unified logging** — one timestamped format across uvicorn access logs, httpx outbound requests, and app code (see `logging_config.py`).
- [x] Docker Compose stack
- [x] CI: test workflow + cross-platform binary release workflow

### AI providers (6 families)
- [x] **Six provider families** — Mock, OpenAI-compatible (+ presets for OpenAI/OpenRouter/Groq/Together/Mistral/DeepSeek/xAI/Fireworks/Z.ai), Ollama, Anthropic (native Messages API), Google Gemini (native generateContent), Cohere (native /v1/chat)
- [x] **Live AI provider configuration** — pick provider/model/key from the Settings UI (persisted to `~/.skillforge/config.json`, chmod 600); planner honors it at runtime without restart
- [x] **Auto-bootstrapped skill-creator skill** — generated & installed on first run (self-bootstrapping)
- [x] **AI tool suggestions** — reload/swap tools via the suggest endpoint + UI panel
- [x] **Connection probing** — `/models` + chat-completions fallback so Z.ai (no /models) tests cleanly

### Skill editing & versioning
- [x] **Skill editing + auto version bump** — re-open installed skills in the builder; reinstall auto-bumps the version (patch/minor/major) based on the diff (textual → patch, tools → minor, identity → major)

### Generated tools inside skills
- [x] **Runnable tool artifacts** — skills include real, working scripts (FastAPI `dev_server.py`, Alembic `migrate.sh`, pytest `test.sh`, Dockerfile, CI YAML, pyproject.toml, CLI, MCP server, etc.) via `ToolArtifactRegistry`
- [x] **Safe tool execution** — opt-in executor with allowlist, 30s timeout, dry-run preview, and audit log (no auto-execution)

### Eval & benchmark harness
- [x] **Eval harness** — run skills vs prompt suites, LLM-as-judge scoring, persisted runs, side-by-side compare with winner highlighting + manual override
- [x] **Slow-provider resilience** — split httpx timeouts (connect/read/write/pool), SKILL.md context truncation, per-provider `max_tokens` cap, and tunable eval budget so Z.ai/GLM and large Ollama models finish within the read timeout

### Marketplace & sharing
- [x] **Local marketplace bridge** — secure pairing (6-char CSPRNG code, single-use, 10-min TTL), scoped bridge tokens (SHA-256 hashed, revocable), approval queue, `.skillpkg` tarball format
- [x] **LocalStubAdapter** — offline reference marketplace implementation (no cloud backend required)
- [x] **Marketplace UI** — publish, browse, search, install-with-approval, connection panel

### AI tool integration
- [x] **Symlink deployment** — auto-detect installed AI coding tools (Claude Code, ZCode, Codex, Cursor, etc.) and symlink a skill into each tool's skills directory from a single source

### Security
- [x] **Local-origin guard** — blocks browser requests from non-local origins (CSRF / DNS-rebinding defense for the token-less local endpoints); same mitigation Jupyter & VS Code use
- [x] **Pairing rate limiting** — 10 attempts/min per client makes the 6-char code brute-force provably infeasible
- [x] **Constant-time token validation** — `hmac.compare_digest` on the SHA-256 hash comparison
- [x] **localhost bind default** (`127.0.0.1`) + explicit CORS allowlist (no wildcard+credentials)
- [x] **Path-traversal guards** on install/validate/preview

### Polish
- [x] **Light/dark/system theme** — persisted, no-flash
- [x] **Real configured paths in UI** — `~/.skillforge/skills` shown live via `GET /api/settings/paths`

### Tests
- [x] **244 tests passing** across 22 files (planner, generator, installer, validator, registry, catalog, all 6 providers, marketplace pairing/packaging/bridge/approvals, eval, security middleware, rate limiting, timeouts, logging, atomic install, SQLite WAL, async handlers, mock-fallback signal)

---

## Planned (v1.x+)

### Trust & safety (Tier 0 from the deep review) ✅
These were the items from [`docs/improvement-plan.md`](./improvement-plan.md) that could lose data or mislead. All four are now fixed.

- [x] **0.1 Async handlers do blocking I/O on the event loop** — wrapped the 5 blocking handlers (`plan-skill`, `suggest-tools`, `eval/run`, `provider/test`, `models`) in `run_in_threadpool` so slow provider calls no longer freeze the event loop. Chose threadpool over a full async refactor for minimal blast radius.
- [x] **0.2 Silent mock fallback misleads users** — `get_active_provider()` now logs the fallback at WARNING; new `get_provider_status()` exposes `effective`/`degraded`/`fallback_reason`; the ChatPanel and Settings page show an amber "Running in mock mode" banner; `planner_model` stamps `"mock"` (not the user's configured model) on the mock path.
- [x] **0.3 Non-atomic install can delete a skill mid-failure** — install now writes to a staging dir + atomic `os.replace`; `remove()` deletes the registry row before rmtree; `_compute_bump` raises on malformed YAML instead of silently skipping.
- [x] **0.4 SQLite missing WAL** — a SQLAlchemy `connect` listener sets `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`, `foreign_keys=ON` on every connection. No more "database is locked" under the eval runner's concurrent transactions.

### Generated skill quality (Tier 1)
- [ ] **1.1 Stack-specific code scaffolds** — the tool artifacts are real scripts, but example prompts/templates are still generic per-domain. Make the FastAPI scaffold genuinely runnable as a starter.
- [ ] **1.2 Per-domain best practices & output standards** — eval judges currently use one shared standards list; specialize per domain.
- [ ] **1.3 Brand-aware name casing** — "FastAPI" not "Fastapi", "PostgreSQL" not "Postgresql".
- [ ] **1.4 Register `pascal_case` as a Jinja filter** — latent bug; filter is referenced but not registered.
- [ ] **1.5 Polish the 3 example skills by hand.**

### Eval robustness (Tier 2)
- [ ] **2.1 Self-grading bias** — the eval judge uses the same provider that generated the response. Let the judge use a different provider/model than the generator.
- ~~2.2 Split httpx timeouts~~ ✅ fixed. ~~2.3 Per-call timeout + run deadline~~ ✅ fixed.
- [ ] **2.4 Guard SkillPreview against out-of-order responses** — fast edits can overwrite a slow in-flight response.
- [ ] **2.5 Eval compare keyed on prompt text** — collision risk when suites share prompt strings; key on `(prompt, index)`.

### UX (Tier 3)
- [ ] **3.1 Data layer (SWR/React Query) + global error boundary** — replace ad-hoc `useEffect` fetches.
- [ ] **3.2 Mobile: hover-only actions unreachable on touch.**
- [ ] **3.3 Accessibility gaps** — keyboard nav, screen-reader labels.
- [ ] **3.4 Replace `window.location.href` reloads with client nav.**

### Release & community
- [ ] **Cross-platform binary releases** — CI (GitHub Actions) builds macOS, Linux, Windows binaries on tag push → GitHub Releases. The build itself ships; this is release automation.
- [ ] **Streaming plan responses** — Server-Sent Events for the chat panel.
- [ ] **Pluggable output formats** — emit MDX or JSON in addition to markdown.
- [ ] **Multi-language catalog contributions** — PR template + CI check for catalog edits.
- [ ] **Offline LLM model picker** — detect installed Ollama models, offer them in the UI.
- [ ] **Eval export** — download runs as CSV/JSON (data is in the API; UI button is the gap).
- [ ] **Statistical eval** — multiple judge samples + significance for noisier models.
- [ ] **Web smoke tests (Playwright)** + snapshot tests for generated SKILL.md.

---

## Considered but not committed (v2+)

- [ ] Team sharing via a shared skills directory (still local, no cloud).
- [ ] Skill dependency graph (one skill composing another).
- [ ] A "skill linter" CI action usable in external repos.
- [ ] Pluggable marketplace adapters beyond LocalStub (e.g. a read-only public registry).

---

## Out of scope (by design)

These will **not** be built, to keep SkillForge local-first, simple, and safe:

- Cloud sync of generated skills.
- Multi-user workspaces.
- Authentication and authorization (the local-origin guard + pairing flow is the extent of access control; this is a local tool).
- Team permission systems.
- Remote/hosted deployment as a managed service.
- **Auto-executing generated scripts** — the tool executor requires explicit `confirm=True` and an allowlist; it will never run code on its own.
- A complex plugin runtime.
- Enterprise dashboard / billing.

If any of these matter to you, SkillForge's permissive MIT license and clean service layer make it straightforward to fork.

---

## OSS release checklist

Before tagging v1.0:
- [ ] `SECURITY.md` — document the threat model (local-first, 127.0.0.1, browser CSRF is the primary threat, mitigated by the origin guard).
- [ ] `CONTRIBUTING.md` — dev setup, test/build commands, code-review norms.
- ~~Tier 0.1–0.4 (data safety)~~ ✅ all fixed.
- [ ] License scan of bundled dependencies (PyInstaller bundles third-party code).
- [ ] Signed releases (cosign / GPG) for the binaries.
