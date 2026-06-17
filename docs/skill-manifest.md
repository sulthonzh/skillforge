# Skill Manifest Format

The `config.yaml` in every generated skill is the single source of truth for what the skill is, which tools it targets, and how it behaves. SkillForge generates it, the validator checks it, and the installer writes it.

## Top-level shape

```yaml
schema_version: "1.0"

skill:        # identity
ai:           # provenance
tools:        # the specific, tool-driven stack
architecture: # recommended patterns
workflow:     # ordered steps
best_practices:
output_standards:
outputs:      # required files & directories
safety:       # execution policy
example_prompts:
example_outputs:
```

## `skill`

```yaml
skill:
  name: backend-fastapi-postgres   # REQUIRED, kebab-case, ≥2 segments, not generic
  title: Backend FastAPI Postgres Skill
  domain: Backend Engineering      # REQUIRED, non-empty
  description: …
  version: "0.1.0"
  status: draft
```

**Naming rules** (enforced by the validator):

- Must match `^[a-z][a-z0-9]+(?:-[a-z0-9]+)+$` (kebab-case, ≥2 segments).
- Rejected as too generic: `fullstack`, `backend`, `frontend`, `data`, `devops`, `general`, `engineering`, `skill`, `default`, `generic`, `template`, `api`, `service`, `app`, `application`.
- Good: `backend-fastapi-postgres`, `data-airflow-dbt-bigquery`, `ai-rag-langchain-pgvector`.

## `tools`

A list of specific tools. At least **two** must be `enabled`.

```yaml
tools:
  - name: FastAPI
    category: frameworks
    enabled: true
    reason: Modern async Python API framework with automatic OpenAPI docs.
```

## `architecture`, `workflow`, `best_practices`, `output_standards`

Free-text lists. The workflow should reference the chosen tools.

```yaml
architecture:
  patterns: [Layered Architecture, Domain-Driven Design, Test-Driven Development]
workflow:
  - Clarify API requirements.
  - Design domain models.
  - …
best_practices:
  - Keep business logic separate from framework code.
output_standards:
  - Clear technical explanation.
```

## `outputs`

The files/directories the skill must contain.

```yaml
outputs:
  required_files: [SKILL.md, README.md, config.yaml]
  required_directories: [prompts, templates, scripts, examples]
```

## `safety`

SkillForge is safe by default. These flags are informational but enforced in spirit by the generator (it never emits executable hooks).

```yaml
safety:
  auto_execute_scripts: false
  require_user_confirmation_before_install: true
  allow_network_access: false
```

## `SKILL.md` required sections

The validator checks that `SKILL.md` contains these headers (case-insensitive):

- `Purpose`
- `When to Use`
- `Tools and Stack`
- `Workflow`
- `Best Practices`
- `Output Standards`

## Validation summary

A skill is **valid** when:

1. `SKILL.md`, `README.md`, `config.yaml` all exist.
2. `config.yaml` parses as YAML and is a mapping.
3. `skill.name` is kebab-case and not generic.
4. `skill.domain` is non-empty.
5. At least two enabled tools.
6. `workflow` is non-empty.
7. `SKILL.md` has all required sections.
