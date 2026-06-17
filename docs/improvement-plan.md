# SkillForge Improvement Plan (v2)

Synthesized from a deep-dive review: my direct inspection + three specialist
audits (skill-generation quality, web UX, backend robustness). Prioritized by
impact on the product's core value — the **quality of the skills it generates**
— and on **not betraying user trust**.

Severity: 🔴 high-impact / trust-breaking · 🟡 medium · 🟢 polish

---

## Tier 0 — Trust & safety (ship first; these can lose data or mislead)

### 0.1 🔴 Async handlers do blocking I/O on the event loop
**Bug:** Every router handler is `async def` but calls blocking work (LLM `httpx.post`, SQLite) inline. FastAPI runs `async def` on the event-loop thread, so **one slow LLM call (60–120s) freezes the entire server** — `/health`, all other requests, everything. A `def` handler would auto-threadpool; the `async` defeats that.
**Files:** `routers/eval.py:118` (`runner.run`), `routers/chat.py:24` (`planner.plan`), `routers/skills.py:50`, `routers/settings.py:191`.
**Fix:** Either drop `async` from handlers that don't `await`, or wrap blocking calls in `await anyio.to_thread.run_sync(...)`. Mechanical, low-risk, unblocks every concurrency improvement after it.

### 0.2 🔴 Silent mock fallback misleads users
**Bug:** `get_active_provider` (`ai_provider.py:485`) catches `AIProviderError` and silently returns the env/mock provider. A user with a bad Anthropic key gets **mock-quality plans/evals with no warning**, and those eval results are persisted under `provider="mock"`, polluting `/api/eval/compare` with fake data mistaken for real output. `runner.py:121` then short-circuits to mock responses with `status="ok"`.
**Fix:** For user-initiated actions (plan/eval from HTTP handlers), error loudly (502) instead of falling back — `chat.py:25` already does this for planning. Reserve the mock fallback for system actions (bootstrap only). Add a `degraded`/`provider_status` field to responses so the UI can show a "running in mock mode (key invalid)" banner.

### 0.3 🔴 Non-atomic install can delete a skill mid-failure
**Bug:** `skill_installer.py:90` does `shutil.rmtree(target)` **before** `_write_files` (`:93`). If the write fails partway (disk full, permission), the user is left with **no skill** where there was one, while the registry row still points at the now-missing path. The version-bump read of the prior `config.yaml` (`:112-143`) also silently skips the bump on a malformed YAML.
**Fix:** Write to a sibling temp dir, then `os.replace` atomically. Validate the prior config before deleting.

### 0.4 🔴 SQLite missing WAL → `database is locked` under concurrency
**Bug:** `database.py:93` creates the engine with only `check_same_thread=False`, no pragmas. Default rollback journal means two concurrent writers (e.g. an eval run + a suite edit) hit `OperationalError: database is locked` with no busy_timeout to wait. The eval runner opens **three separate** `session_scope()` blocks per run (`runner.py:210/224/233`).
**Fix:** Enable `PRAGMA journal_mode=WAL; busy_timeout=5000; synchronous=NORMAL;` via a SQLAlchemy `connect` event in `get_engine()`. 5-line change.

### 0.5 🔴 Security: 0.0.0.0 bind + CORS `*` + credentials + path traversal
**Bug (4 issues):**
1. `settings.py:58` defaults `api_host=0.0.0.0` — anyone on the LAN can hit `/api/settings/paths` (leaks local FS paths), enumerate models using the user's key, or install skills. No auth at all.
2. `main.py:70` — `allow_origins=["*"]` + `allow_credentials=True` is an invalid Fetch-spec combo and a CSRF footgun: any website can `POST /api/skills/install` or `PUT /api/settings/provider` (set an attacker's key) on locally-running SkillForge.
3. `main.py:131` — the SPA catch-all does `web_dir / full_path` then `.is_file()` with **no `..` sanitization**. A misconfigured `static_dir` near user data could serve arbitrary files. `Path("../../etc/passwd")` resolves happily.
4. `user_config.py:195-207` — `chmod 0600` runs *after* `write_text`, leaving a world-readable window; no-op on Windows.
**Fix:** Bind `127.0.0.1` by default (override for Docker); scope CORS to explicit localhost origins in non-bundled mode; add `(candidate.resolve()).is_relative_to(web_dir.resolve())` before `FileResponse`; write config via `os.open(fd, 0600)` then `os.write`.

---

## Tier 1 — Generated skill quality (the product's core value)

### 1.1 🔴 Stack-specific code scaffolds (not generic stubs)
**Bug:** Scaffolds are toy stubs. A "Next.js" skill emits a plain React component (no `"use client"`, no App Router). A FastAPI router has no Pydantic models/DI. `_PIPELINE` is `extract()/transform()/load()` with `pass`. `_RAG_CHAIN` is `raise NotImplementedError`. Worse: **any Python skill gets `service.py.j2`+`repository.py.j2` even if the domain is testing/observability/AI** — actively harmful scaffolds. `_template_files` (`skill_generator.py:159`) keys only on language, not domain.
**Fix:** Replace the language-keyed scaffold selection with a **domain+tool-aware scaffold registry**:
- `fastapi` tool → router with Pydantic request/response models + `Depends` injection
- `nextjs` tool → App-Router `"use client"` page component
- `airflow` tool → DAG with `@dag`/`@task` decorators
- `langchain` tool → RAG chain with retriever + prompt template (implemented, not NotImplementedError)
- `terraform` tool → provider + resource blocks, not an empty `terraform{}`
- Gate backend scaffolds (service/repository) to the **backend** domain only.

### 1.2 🔴 Per-domain best practices & output standards
**Bug:** `DEFAULT_BEST_PRACTICES` and `DEFAULT_OUTPUT_STANDARDS` (`ai_skill_planner.py:136-151`) are **single global lists** pasted into every skill. A data skill and a frontend skill get identical "Keep business logic independent of framework code" and "Add observability before going to production" (meaningless for UI). This is the #1 thing that makes skills feel templated.
**Fix:** Promote them to per-domain dicts (`DEFAULT_BEST_PRACTICES[domain]`, `DEFAULT_OUTPUT_STANDARDS[domain]`) like `DEFAULT_WORKFLOW`/`DEFAULT_PATTERNS` already are. Each domain gets genuinely different guidance.

### 1.3 🔴 Brand-aware name casing
**Bug:** `_title_case` (`:509`) naively capitalizes: `fastapi`→"Fastapi", `postgresql`→"Postgresql", `nextjs`→"Next Js". Loses brand identity in titles and reasons.
**Fix:** Add a `BRAND_CASING` dict (`{"fastapi":"FastAPI","postgresql":"PostgreSQL","opentelemetry":"OpenTelemetry","nextjs":"Next.js",…}`) used by `_title_case`, slug display, and `_reason_for`. Maintained alongside the catalog.

### 1.4 🔴 Register `pascal_case` as a Jinja filter (latent bug)
**Bug:** Scaffolds use `{{ x | pascal_case }}` but it's a Python function, not a registered filter → `UndefinedError` if rendered.
**Fix:** Register `pascal_case` (+ `kebab`/`snake`) on the Jinja `Environment` in `template_renderer.py`.

### 1.5 🟡 Polish the 3 example skills by hand
**Bug:** Examples are raw generator output: generic descriptions ("Helps engineers with backend engineering work. Based on: …"), wrong title casing ("Backend Fastapi Postgresql Skill"). These are users' first impression.
**Fix:** Hand-edit `examples/*/SKILL.md`+`README.md` to be genuinely good reference skills.

### 1.6 🟡 Mock provenance honesty
**Bug:** `_resolve_planner_model` reads UI config and stamps `planner_model="glm-5.2"` on mock output even though no LLM ran. Footer claims "Generated by SkillForge using model glm-5.2."
**Fix:** Mock output should stamp `planner_model="mock"`.

### 1.7 🟡 Name derivation drops relevant tools / adds irrelevant ones
**Bug:** `_derive_skill_name` priority list omits `styling`/`e2e`/`components`, so Next.js+Tailwind loses Tailwind. It force-inserts a language, so a Playwright-e2e ask gains "python". The fill heuristic adds redundant tools (Playwright AND Cypress).
**Fix:** Expand the priority list; don't force-insert languages; dedupe by semantic role.

---

## Tier 2 — Robustness

### 2.1 🔴 Eval judge uses the same provider that generated (self-grading bias)
**Bug:** `runner.py:125` generates with `self._provider`; `:130` judges with the **same** provider. Known LLM-as-judge biases: self-preference (a model rates its own style higher), shared failure mode (weak model produces weak output *and* can't judge). This makes `/api/eval/compare` not a fair cross-model comparison — its entire purpose.
**Fix:** Add an optional `judge_provider`/`judge_model` config (defaults to active provider). Store `judge_provider`/`judge_model` columns on `EvalRunRecord` (currently only `provider`/`model`). Document the self-grading caveat in the UI when judge == generator.

### 2.2 🟡 Split httpx timeouts + shared client
**Bug:** Flat `timeout=60.0` sets connect/read/write/pool all to 60s. A hung TCP connect blocks 60s per call. Clients are created per-call (no keep-alive across an eval run's ~100 calls).
**Fix:** `httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)`; a shared long-lived `httpx.Client` per provider instance.

### 2.3 🟡 Eval runner: per-call timeout + run deadline
**Bug:** No per-call timeout beyond the provider's; no wall-clock deadline. 50 prompts × (60s+60s) = ~100 min blocking (compounds with 0.1).
**Fix:** Per-call deadline (e.g. 30s); mark `status=error` on timeout; optional bounded concurrency for prompts.

### 2.4 🟡 Guard SkillPreview against out-of-order responses
**Bug:** `SkillPreview.tsx:17-46` debounce cleanup guards the timeout but **not** the in-flight `api.preview()` promise. Two edits → two in-flight fetches → last-resolved wins, not latest-requested.
**Fix:** `AbortController` per effect run + `.abort()` in cleanup, and/or capture signature at call time and ignore mismatches.

### 2.5 🟡 Eval compare keyed on prompt text (collision risk)
**Bug:** `routers/eval.py:294,301` matches results by prompt-string equality. Two suites sharing a prompt string merge into one row; cross-suite responses can mix.
**Fix:** Add a `prompt_hash`/`prompt_id` to `EvalResultRecord`; key the matrix on that, not free text.

---

## Tier 3 — UX (from the frontend audit)

### 3.1 🔴 Add a data layer (SWR/React Query) + global error boundary
**Bug:** No data layer — every component fetches once on mount into local state; no `router.refresh()`, no refetch. This causes a **cluster** of bugs: stale data after install (home "Recent" doesn't update; eval dropdown doesn't see new skills), the SkillPreview race, loading/empty-state flashes, and "error vanishes in 4.5s." No `app/error.tsx` means one render exception blanks the whole app.
**Fix (single highest-leverage UX change):** Add SWR (or React Query) + `app/error.tsx`. `mutate`/`invalidate` from install/remove/run cascades to all consumers; cached errors persist with Retry; `isLoading` vs `data===[]` fixes empty-state flashes. Retires more visible bugs than any other intervention.

### 3.2 🟡 Mobile: hover-only actions unreachable on touch
**Bug:** `ToolRecommendationCard.tsx:57` and `InstalledSkillList.tsx:148` use `opacity-0 group-hover:opacity-100`. On touch devices there's no hover → **edit/remove are unreachable on phones/tablets**. Blocks core workflows on mobile.
**Fix:** Always show actions on touch (e.g. `opacity-100 sm:opacity-0 sm:group-hover:opacity-100`).

### 3.3 🟡 Accessibility gaps
- `toast.tsx:60` — errors use `role="status"`; should be `role="alert"`. Viewport needs `aria-live`.
- `tabs.tsx` — no `role="tabpanel"`, no `aria-controls`/`aria-labelledby`, no arrow-key nav.
- `eval/page.tsx:323` — compare skill-picker buttons have no `aria-pressed`/`role="checkbox"`.
- `settings/page.tsx:218` — provider cards have no `role="radiogroup"`/`radio`/`aria-checked`.
- Collapsible sections (`SkillManifestEditor:238`, `SuggestToolsButton:301`) lack `aria-expanded`/`aria-controls`.
- Score color-only signaling (no icon for warn-vs-pass) — fails color-blind users.
- No `aria-current="page"` on active nav; no skip-to-main link.

### 3.4 🟢 Replace `window.location.href` reloads with client nav
`app/skill/page.tsx:45` uses full-page reload after remove; loses SPA state.

---

## Tier 4 — Test coverage

### 4.1 🟡 Web smoke tests (Playwright)
**Gap:** 137 backend tests, **zero UI tests**.
**Fix:** Small Playwright suite: load `/`, type a prompt, assert skill name appears; load `/eval`, run against mock, assert a score renders.

### 4.2 🟢 Snapshot tests for generated SKILL.md
Guard against the generator silently producing worse output. Snapshot the 3 example skills' SKILL.md; fail on unexpected drift.

---

## What the review did NOT find (good news)
- No data-loss bugs in the transactional paths (installer/registry/eval all commit cleanly *when not concurrent*).
- The LLM path (when a real provider is configured) produces **genuinely good, specific** output — the product's ceiling is high.
- Domain-specific workflows ARE present (verified per-domain).
- All 6 providers, eval, settings, compare work end-to-end.

## Recommended execution order
1. **Tier 0 (0.1–0.5)** — trust & safety. The async/blocking fix (0.1) unblocks everything.
2. **Tier 1 (1.1–1.4)** — the biggest quality jump for generated skills.
3. **Tier 3.1** — data layer + error boundary (fixes the largest UX bug cluster).
4. **Tier 1 (1.5–1.7) + 2.1** — polish + judge independence.
5. **Tier 2 (2.2–2.5) + 3.2–3.4** — robustness + mobile/a11y.
6. **Tier 4** — lock in the gains with tests.
