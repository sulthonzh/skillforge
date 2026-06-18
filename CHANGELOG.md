# Changelog

All notable changes to SkillForge are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- **Eval judge robustness** — when the LLM-as-judge returns an empty/non-JSON
  response (seen on Z.ai/GLM), the eval now retries with a plain-text judge
  and extracts the score via regex, instead of marking a good response as
  failed. (`ebf0e7f`)
- **Slow-provider eval timeouts** — split `httpx.Timeout` (connect=10s,
  read=180s), truncate SKILL.md context to 4000 chars, and cap `max_tokens`
  per provider call. Eval failures dropped from 5/8 to 0/8 on Z.ai/GLM.
- **Marketplace duplicate listings** — listing IDs are now keyed on skill
  name (stable), and re-publishing sweeps stale legacy-hash entries.
- **Bridge token pollution** — marketplace tests no longer write to the real
  `~/.skillforge` store; all tests use isolated temp-dir fixtures.
- **Binary crash (`jaraco.text`)** + **71MB → 22MB bloat** — excluded
  `pkg_resources`/`setuptools`/`jaraco` and heavy unused packages
  (botocore, numpy, matplotlib, psycopg2, lxml, PIL) from the PyInstaller
  spec; added build guards to prevent regression.

### Security
- **Local-origin guard** — new middleware blocks browser requests from
  non-loopback origins (CSRF / DNS-rebinding defense).
- **Pairing rate limiting** — 10 attempts/min on pairing endpoints.
- **Constant-time token validation** — `hmac.compare_digest` on hash comparison.
- **Mock-fallback warning** — when the configured AI provider fails to
  initialize, the UI now shows an amber "Running in mock mode" banner instead
  of silently serving heuristic output.

### Trust & safety (Tier 0)
- **Atomic install** — install writes to a staging dir + `os.replace`; a
  mid-write failure no longer deletes the existing skill.
- **SQLite WAL** — enabled `journal_mode=WAL` + `busy_timeout=5000` to
  eliminate "database is locked" under concurrent eval/registry access.
- **Non-blocking event loop** — all 5 blocking provider handlers wrapped in
  `run_in_threadpool`; a slow LLM call no longer freezes the whole server.

### Infrastructure
- **Unified logging** — one timestamped format across uvicorn, httpx, and app
  code (was three different interleaved formats).
- **247 tests** passing across 22 test files.

## [0.1.0] — Initial MVP

### Added
- Local Web UI (Next.js 14 + TypeScript + Tailwind)
- Local backend API (FastAPI)
- Chat-based AI skill planning (mock + LLM planner)
- Six AI provider families (Mock, OpenAI-compatible, Ollama, Anthropic, Gemini, Cohere)
- Editable manifest with auto semantic version bumping
- Eval & benchmark harness with LLM-as-judge scoring and side-by-side compare
- Local marketplace bridge (pairing, scoped tokens, approval queue, `.skillpkg`)
- Runnable tool artifacts inside skills (FastAPI server, Alembic, pytest, Dockerfile, MCP server)
- Symlink deployment to AI coding tools (Claude Code, ZCode, Codex, Cursor)
- Single-binary distribution (PyInstaller, 22MB, no Python/Node required)
- Light/dark/system theme
- Docker Compose stack
- CI test workflow + cross-platform binary release workflow
