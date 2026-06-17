# Tool Catalog

The tool catalog is the knowledge base the AI planner consults to recommend specific tools. It lives at:

```
apps/api/skillforge_api/data/tool_catalog.yaml
```

It is a plain YAML file so OSS contributors can extend SkillForge without writing code.

## Structure

```yaml
schema_version: "1.0"

domains:
  <key>:                       # internal key; also matched against user text
    label: <Human Label>       # stored on the manifest, shown in the UI
    keywords: [...]            # extra hints for the domain classifier
    recommended_tools:
      <category>:              # e.g. languages, frameworks, databases, orm, …
        - <ToolName>           # exact name used in generated manifests
```

A tool may appear under multiple domains (e.g. `PostgreSQL` is in both `backend.databases` and `data_engineering.warehouses`). The matcher dedupes.

## Categories

Categories are free-form strings, but the planner and generator recognize these common ones:

| Category       | Example tools                     |
| -------------- | --------------------------------- |
| `languages`    | Python, Go, TypeScript, SQL       |
| `frameworks`   | FastAPI, Django, Next.js, Gin     |
| `databases`    | PostgreSQL, MySQL, Redis, MongoDB |
| `orm`          | SQLAlchemy, Prisma, GORM          |
| `migration`    | Alembic, Flyway                   |
| `testing`      | Pytest, Jest, Playwright          |
| `container`    | Docker                            |
| `cicd`         | GitHub Actions, GitLab CI         |
| `observability`| OpenTelemetry, Prometheus, Grafana|
| `orchestration`| Airflow, Dagster                  |
| `transformation`| dbt, Pandas, Spark               |
| `warehouses`   | BigQuery, Snowflake, ClickHouse   |
| `iac`          | Terraform, Pulumi                 |
| `vector_databases` | pgvector, Qdrant, Chroma     |

## How matching works

1. **Domain classification** — `find_domain(text)` lowercases the message and scores each domain by counting occurrences of the domain key, label, and keywords. A direct hit on the key/label gets a +10 boost.
2. **Tool detection** — `find_tools_in_text(text)` runs word-boundary matching so multi-word tokens (`GitHub Actions`) and tokens with trailing punctuation (`FastAPI,`) match, while short tokens (`Go`) don't false-positive on common words (`going`).

## Extending the catalog

Add a domain or tool and the planner considers it immediately. Example:

```yaml
domains:
  security:
    label: Security Engineering
    keywords: [appsec, secrets, sast, vulnerability, supply-chain]
    recommended_tools:
      languages: [Python, Go]
      sast: [Semgrep, Bandit]
      secrets: [TruffleHog, Gitleaks]
      sbom: [Syft, CycloneDX]
```

Then add a test in `apps/api/tests/test_tool_catalog.py` if you introduce a new category. See [CONTRIBUTING.md](../CONTRIBUTING.md).
