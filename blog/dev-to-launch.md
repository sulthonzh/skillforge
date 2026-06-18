---
title: "I built a Homebrew for AI skills: install flow and eval harness inside"
published: false
description: "SkillForge is a local-first OSS tool that turns a plain-English engineering need into installable SKILL.md, README.md, and config.yaml files. Six LLM providers, LLM-as-judge eval harness, marketplace bridge with scoped tokens."
tags: showdev, opensource, ai, llm
---

## The problem

Last quarter I spent an afternoon writing a SKILL.md for backend FastAPI work by hand. By the time I had a usable prompt set, three templates, and a config file, I realized nobody else on the team would ever do this. Engineering skills are either too rigid, a hand-written prompt for one specific stack, or too generic, a "full-stack" skill that tells you to "use best practices." The GPT Store proved the failure mode in public: when quality is not measurable, prompt wrappers win and nobody comes back.

SkillForge is my attempt at a fix. Install is two pip commands and a serve:

```bash
cd apps/api && pip install -e ".[dev]"
cd ../cli   && pip install -e .
skillforge serve --build-web    # → http://localhost:8000
```

The thing I kept hitting was the category axis. I wanted a skill for a specific stack, FastAPI plus Postgres plus Alembic plus pytest plus Docker, but every skill marketplace wanted me to pick a category first. Categories are the wrong axis. Skills should be named after the stack they target, the way Homebrew formulae are named after the binary they install. A skill called `backend-fastapi-postgres` is honest about what it does. A skill called "Senior Backend Engineer" is vibes.

The GPT Store angle was the other half. When you cannot measure skill quality, the people who optimize for thumbnails win. The people who optimize for output leave. The marketplace fills with wrappers and stays that way.

## The idea

Flip the workflow. Describe the need in plain English. The planner picks the tools and explains each pick. The generator produces a focused skill. Skills are named for their stack, not for a persona:

`backend-fastapi-postgres`, `data-airflow-dbt-bigquery`, `devops-kubernetes-helm-terraform`, `ai-rag-langchain-pgvector`, `observability-opentelemetry-grafana`, `web-scraping-python-playwright`.

Local-first means local-first. SkillForge binds to `127.0.0.1`, ships no telemetry, and does not auto-execute generated scripts. The only outbound traffic is to the LLM provider you configure. Skills land on disk under `~/.skillforge/skills`. The filesystem is the source of truth.

## How it works

Three apps, one service layer. The CLI and the API import the same Python services, so `skillforge plan` on the command line and `POST /api/chat/plan-skill` from the browser run the exact same code path.

```
┌──────────────────────────────────────────────────────────────────┐
│  apps/web   (Next.js + TS + Tailwind)   :3000 / :8000 (bundled)  │
│  ChatPanel → ManifestEditor → SkillPreview → InstallButton       │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼─────────────────────────────────────┐
│  apps/api   (FastAPI)                       :8000                │
│  routers/  ──►  services/  ──►  repositories/                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │ reuses the same service layer
┌────────────────────────────▼─────────────────────────────────────┐
│  apps/cli   (Typer + Rich)                                       │
│  serve | plan | generate | install | list | validate | remove    │
└──────────────────────────────────────────────────────────────────┘
```

Six provider families ship today, all swappable live from the Settings page with no restart: Mock (default, offline, deterministic), OpenAI-compatible (OpenAI, OpenRouter, Groq, Together, Mistral, DeepSeek, xAI, Fireworks, Z.ai), Ollama, Anthropic, Gemini, and Cohere. The Mock provider is the reason the project runs with zero configuration and the reason the test suite passes offline.

A first plan:

```bash
skillforge plan "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
```

The CLI surface is intentionally small: `serve`, `plan`, `generate`, `install`, `list`, `validate`, `remove`. The generator is pure with respect to execution. It never calls `subprocess`. The `scripts/` directory it writes is reference text on disk, runnable when you choose to run it.

## What you actually get

A skill lands at `~/.skillforge/skills/<name>/` with this shape:

```
~/.skillforge/skills/backend-fastapi-postgres/
  SKILL.md
  README.md
  config.yaml
  prompts/
  templates/
  scripts/      # real FastAPI server, Alembic, pytest, Dockerfile, MCP server
  examples/
```

The `scripts/` directory is the part that took the longest. Each artifact is a real, runnable file produced by a `ToolArtifactRegistry` at generation time, not a placeholder. The FastAPI skill ships a working `dev_server.py`. The data skill ships an Alembic `migrate.sh`. The devops skill ships a Helm `Chart.yaml`. The `config.yaml` is a manifest, not a config dump:

```yaml
schema_version: "1.0"
skill:
  name: backend-fastapi-postgres
  domain: Backend Engineering
tools:
  - name: Python
    category: language
    reason: Primary language for this backend skill.
safety:
  auto_execute_scripts: false
  require_user_confirmation_before_install: true
```

Every generated skill carries the `safety` block. `auto_execute_scripts` is always false. The installer will not overwrite an existing skill without an explicit flag.

## The analogy

SkillForge is not a new shape. It is the same shape as four package managers you already know.

| SkillForge | Homebrew | npm | VS Code | Helm |
|---|---|---|---|---|
| `config.yaml` | formula (.rb) | package.json | package.json (contributes) | Chart.yaml |
| `SKILL.md` | install block | main / bin | extension.ts | templates/ |
| `scripts/` | resource blocks | bin/ | bundled commands | n/a |
| `~/.skillforge/skills` | Cellar | node_modules | ~/.vscode/extensions | release namespace |
| `.skillpkg` tarball | bottle | pack tarball | .vsix | chart .tgz |
| marketplace bridge | tap (git repo) | scoped pkg + token | Marketplace publisher | OCI registry |
| `skillforge validate` | `brew audit` | `npm publish --dry-run` | vsce package | `helm lint` |

Homebrew taps federate anyone's git repo of formulae (https://docs.brew.sh/Formula-Cookbook). npm scoped packages use auth tokens for verified namespaces. Helm OCI registries host signed charts. The SkillForge marketplace bridge is the same model: anyone can host a marketplace, and the local app pairs with it via a 6-character code.

## The marketplace vision

The marketplace is not a website. It is an HTTP contract. Anyone can run one. The local app does not care whose marketplace it is paired with. Today the repo ships a `LocalStubAdapter` that implements the full publish, search, download, install flow offline, so you can try the entire loop without a cloud backend.

The pairing flow borrows from VS Code plus GitHub. The local user generates a single-use 6-character code with a 10-minute TTL:

```
# 1. Local user generates a single-use 6-char code
POST /api/marketplace/pair/code
→ {"code": "AB3X9K", "ttl_minutes": 10}

# 2. User enters the code on the marketplace site

# 3. Marketplace exchanges the code for a 32-byte scoped bearer token
POST /api/bridge/pair/complete
Body: {"code": "AB3X9K", "label": "skillforge-marketplace"}
→ 200: {"token": "<32-byte-urlsafe>", "token_id": "...", "scopes": [...]}
```

Only the SHA-256 hash of the token is stored locally, in a chmod 600 file. Comparison is constant-time via `hmac.compare_digest`. Pairing endpoints are rate-limited to 10 attempts per minute per client, which makes the 887-million code space provably infeasible to brute force.

Default scopes are `registry:read`, `skills:install`, `skills:publish`. The dangerous one, `skills:install:unattended`, is off by default and requires explicit grant. Marketplace-originated installs land in an approval queue. The local user clicks Approve. No silent installs, ever.

The wire bundle is a gzipped tarball called `.skillpkg`:

```
skill-creator.skillpkg
├── PACKAGING        # JSON: name, version, packaged_at, packaged_by
├── manifest.json    # canonical SkillManifest
├── SKILL.md
├── config.yaml
├── prompts/
├── templates/
├── scripts/
└── examples/
```

Path traversal is rejected on unpack. The manifest is the source of truth.

The vision: anyone designs a skill, anyone hosts a marketplace, anyone installs. The reason the GPT Store filled with prompt wrappers is that there was no quality signal. SkillForge ships with one.

## The eval harness

The eval harness is the quality signal. It lives at `/eval` in the Web UI.

Pick a skill. Pick a prompt suite. For each prompt, the harness runs the skill's SKILL.md as guidance against the configured provider, then asks an LLM-as-judge to score the response 0 through 10 against the skill's own `output_standards`. Results stream into an expandable table with color-coded scores and reasoning. Runs persist to SQLite so you can track scores across iterations.

```
POST /api/eval/run
{
  "skill_name": "backend-fastapi-postgres",
  "suite": "general",
  "provider": "anthropic",
  "judge_provider": "openai-compatible"
}
→ 200: {"run_id": "...", "results": [...]}
```

Compare mode is where the harness earns its keep. Pick two or more skills and a shared suite. You get an aggregate score, a win count, and per-prompt side-by-side cards with the winner highlighted. Manual override is supported. When five people publish a `backend-fastapi-postgres` skill, you can run them head to head on the same suite and see which one actually wins. Quality becomes measurable.

The cost guard caps completions per run at `SKILLFORGE_EVAL_MAX_CALLS=50`. Eval never executes generated scripts. It only calls the chat API.

Two honest caveats. The judge and the generator can already be configured to use different providers, which kills the worst of the self-grading bias. The default config still uses the same provider for both, and most users will not change it. The roadmap item Tier 2.1 is to make the judge default to a different provider than the generator. The second caveat: per-domain output standards are still generic. Every domain currently judges against one shared standards list. Tier 1.2 on the roadmap specializes them.

The GPT Store failed partly because there was no quality signal. SkillForge ships with one. It is rough, it has known bias, and it is better than nothing.

## Safety and honest limitations

Safety first. The local server binds to `127.0.0.1` by default. A `LocalOriginGuardMiddleware` rejects browser requests whose `Origin` or `Referer` header names a non-loopback host, which is the CSRF and DNS-rebinding defense Jupyter and VS Code use. Token comparison is constant-time. Install is atomic: write to a staging directory, then `os.replace`. SQLite runs in WAL mode with `busy_timeout=5000` and `synchronous=NORMAL`, so concurrent eval and registry access no longer hits "database is locked." Generated scripts are never executed automatically. The tool executor requires explicit `confirm=True`, an allowlist match, and a 30-second timeout.

Now the limits. These are the engagement magnet, so I will be direct about them:

- Cross-platform binary releases need CI work. The release workflow ships in the repo. The automation that runs it on tag push does not. Today you build the binary on your own platform with `./scripts/build-binary.sh`.
- The skill-creator skill, the meta skill that helps you author new skills, is auto-bootstrapped on first run. It works. It is still rough.
- No streaming SSE yet. Plan responses return as a single JSON payload. The Web UI shows a spinner.
- The web layer has no Playwright coverage. Snapshot tests for generated SKILL.md do not exist.
- The repo has 247 tests passing across 21 files. That number is real, not rounded up.

If you want to find a bug, those bullets are where to look first.

## Roadmap

The big vision is a federated marketplace where anyone can design a skill, publish it, and have end users compare skill outputs head to head. Best skills rise. Weak skills get forked and improved.

Concrete items on the roadmap:

- Streaming plan responses via Server-Sent Events
- Per-domain output standards for the eval judge
- A separate judge provider by default to kill self-grading bias
- Cross-platform binary releases via CI on tag push
- Multi-language catalog contributions with a PR template and CI check
- A "skill linter" CI action usable in external repos
- Pluggable marketplace adapters beyond LocalStub, including a read-only public registry
- Statistical eval with multiple judge samples and significance testing

Out of scope by design: cloud sync, multi-user workspaces, auth, team permissions, remote deployment, auto-executing generated scripts. If those matter to you, the MIT license and the clean service layer make forking straightforward.

## Try it

```bash
git clone https://github.com/sulthonzh/skillforge
cd skillforge
cd apps/api && pip install -e ".[dev]"
cd ../cli   && pip install -e .
skillforge serve --build-web
```

I want bug reports and edge cases, not stars. Tell me where it breaks. Specific things I would like feedback on:

- Did the planner pick the wrong tools for your stack?
- Did the generator produce a script that does not run when you execute it?
- Did the eval judge score something obviously wrong, and against which standards?
- Did the marketplace pairing flow fail on your network setup?
- Did the local-origin guard reject a legitimate tool you use?

The file `apps/api/skillforge_api/data/tool_catalog.yaml` is a great first PR. Add a domain. Add a tool. Add a reason. The catalog is the part that gets better with every contributor.

Repo: https://github.com/sulthonzh/skillforge
