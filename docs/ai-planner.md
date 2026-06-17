# AI Planner

The `AISkillPlanner` turns a natural-language engineering need into a structured `SkillManifest`. It is the brain of SkillForge.

## Responsibilities

1. **Classify the domain** using the [tool catalog](./tool-catalog.md) (`find_domain`).
2. **Recommend specific tools** — first those explicitly mentioned in the message, then top-of-list defaults (one per category) until the stack has ~8 tools.
3. **Explain each choice** with a concrete reason.
4. **Derive a specific skill name** like `backend-fastapi-postgres` — never a generic name.
5. **Produce a manifest** the UI/CLI can edit, preview, validate, and install.

## Provider modes

The planner delegates the "thinking" to an `AIProvider`:

| Provider            | When to use                                   | Needs network? |
| ------------------- | --------------------------------------------- | -------------- |
| `mock`              | Tests, CI, zero-config first run              | No             |
| `openai-compatible` | OpenAI, OpenRouter, Together, Groq, vLLM, ... | Yes            |
| `ollama-local`      | Local LLMs via Ollama                         | No (localhost) |

Configure via `SKILLFORGE_AI_PROVIDER`. The default is `mock` so everything works offline.

### Mock planner

The mock planner is deterministic and uses catalog heuristics:

- `ToolCatalog.find_domain(text)` scores every domain by keyword overlap.
- `ToolCatalog.find_tools_in_text(text)` finds tool names mentioned in the message using word-boundary matching (so "Go" doesn't match "going").
- Missing slots are filled one-tool-per-category from the domain's recommended list.
- Architecture patterns, workflows, best practices, and output standards come from sensible per-domain defaults.

This means the mock planner produces **real, specific, valid manifests** — good enough to exercise the entire pipeline without an API key.

### LLM planner

For real providers, the planner sends a strict system prompt (see `PLANNER_SYSTEM_PROMPT` in `ai_skill_planner.py`) requiring a JSON object with the exact manifest shape. The response is parsed defensively:

- Code fences are stripped.
- Surrounding prose is sliced to the outermost `{` / `[`.
- Fields are coerced into the Pydantic `SkillManifest`.

The planner then re-derives the skill name defensively and stamps provenance (`ai.generated_by`, `planner_model`, `created_at`).

## JSON contract

The planner returns `(SkillManifest, explanation)`. The manifest serializes to the JSON shape consumed by the Web UI:

```json
{
  "skill_name": "backend-fastapi-postgres",
  "title": "…",
  "domain": "Backend Engineering",
  "summary": "…",
  "recommended_tools": [{"name": "FastAPI", "category": "frameworks", "reason": "…"}],
  "architecture_patterns": ["…"],
  "workflow": ["…"],
  "best_practices": ["…"],
  "output_standards": ["…"],
  "files_to_generate": ["SKILL.md", "README.md", "config.yaml"],
  "directories_to_generate": ["prompts", "templates", "scripts", "examples"]
}
```

## Safety

- The planner **never** auto-executes anything. It only produces data.
- It **never** sends local files to the provider — only the user's message and the system prompt.
- It makes **safe assumptions** and asks no follow-up questions in v1.
