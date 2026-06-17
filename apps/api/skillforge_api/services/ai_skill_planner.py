"""AI skill planner.

Turns a natural-language engineering need into a structured
:class:`SkillManifest`. The planner:

1. Classifies the engineering domain using the tool catalog.
2. Recommends *specific* tools (never generic "fullstack").
3. Explains each choice.
4. Produces a manifest the UI can edit.

When the provider is the mock, the planner builds a deterministic, well-formed
manifest from catalog heuristics so the whole pipeline works offline.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from ..schemas.manifest import (
    Architecture,
    Outputs,
    Safety,
    SkillAI,
    SkillManifest,
    SkillMeta,
    Tool,
)
from ..settings import Settings, get_settings
from .ai_provider import AIProvider, AIProviderError, get_provider
from .tool_catalog import ToolCatalog, get_catalog


# ----------------------------------------------------------------------------
# Planner
# ----------------------------------------------------------------------------


class AISkillPlanner:
    """Plans a skill from natural language."""

    DEFAULT_PATTERNS: dict[str, list[str]] = {
        "backend": ["Layered Architecture", "Domain-Driven Design", "Test-Driven Development"],
        "data_engineering": ["Medallion Architecture", "Idempotent Pipelines", "Data Contracts"],
        "devops": ["GitOps", "Infrastructure as Code", "Immutable Infrastructure"],
        "ai_engineering": ["Retrieval-Augmented Generation", "Evaluation-Driven Development", "Prompt Versioning"],
        "testing_qa": ["Test Pyramid", "Behavior-Driven Development", "Shift-Left Testing"],
        "observability": ["Three Pillars (Logs, Metrics, Traces)", "SLO-Driven Operations"],
        "web_scraping": ["Polite Crawling", "Resumable Pipelines", "Schema Validation"],
        "frontend": ["Component Composition", "Accessibility First", "Design Tokens"],
    }

    DEFAULT_WORKFLOW: dict[str, list[str]] = {
        "backend": [
            "Clarify API requirements and consumers.",
            "Design domain models and entities.",
            "Define the database schema.",
            "Implement API routes and the service layer.",
            "Add a repository layer for persistence.",
            "Add database migrations.",
            "Write unit and integration tests.",
            "Add Docker setup for local development.",
            "Configure CI/CD for tests and builds.",
            "Instrument with observability.",
        ],
        "data_engineering": [
            "Profile source systems and define SLAs.",
            "Model the warehouse (staging → marts).",
            "Build ingestion pipelines.",
            "Implement dbt transformations.",
            "Add data-quality checks.",
            "Backfill and validate historical data.",
            "Schedule with an orchestrator.",
            "Add CI/CD for pipeline changes.",
            "Instrument pipelines with observability.",
        ],
        "devops": [
            "Capture environment and compliance requirements.",
            "Provision infrastructure with IaC.",
            "Containerize applications.",
            "Define Helm/Kustomize releases.",
            "Configure CI/CD for deployment.",
            "Set up observability and alerting.",
            "Define secrets management.",
            "Document runbooks.",
        ],
        "ai_engineering": [
            "Define the use case and success metrics.",
            "Choose a retrieval strategy and vector store.",
            "Build ingestion and embedding pipelines.",
            "Implement the retrieval and generation chain.",
            "Add prompt templates and versioning.",
            "Evaluate with golden datasets.",
            "Add observability for traces and feedback.",
            "Configure CI for prompt and eval changes.",
        ],
        "testing_qa": [
            "Identify the test surface and risk areas.",
            "Define the test pyramid per layer.",
            "Write unit tests for pure logic.",
            "Add integration tests for boundaries.",
            "Add end-to-end tests for critical flows.",
            "Wire tests into CI.",
            "Track coverage and flakiness.",
        ],
        "observability": [
            "Identify services and their critical paths.",
            "Instrument metrics, logs, and traces.",
            "Define SLOs and error budgets.",
            "Build dashboards for key journeys.",
            "Configure alerting and runbooks.",
            "Validate with synthetic checks.",
        ],
        "web_scraping": [
            "Define target sites and respect robots.txt.",
            "Choose a scraping strategy (static vs. dynamic).",
            "Implement parsers with schema validation.",
            "Add retries, backoff, and rate limiting.",
            "Store raw and normalized artifacts.",
            "Schedule and monitor the scraper.",
        ],
        "frontend": [
            "Capture design and accessibility requirements.",
            "Scaffold the app and design tokens.",
            "Build accessible component primitives.",
            "Implement routes and data fetching.",
            "Add state management where needed.",
            "Write unit and component tests.",
            "Add end-to-end tests for key flows.",
            "Configure CI/CD and preview deploys.",
        ],
    }

    DEFAULT_BEST_PRACTICES: list[str] = [
        "Keep business logic independent of framework code.",
        "Make every change testable and reversible.",
        "Prefer explicit configuration over implicit magic.",
        "Use structured logging throughout.",
        "Add observability before going to production.",
        "Avoid overengineering early; extract abstractions when patterns repeat.",
    ]

    DEFAULT_OUTPUT_STANDARDS: list[str] = [
        "Clear technical explanation of each choice.",
        "Maintainable, readable code examples.",
        "Testable implementation guidance.",
        "Production-aware recommendations.",
        "Security and reliability considerations.",
    ]

    def __init__(
        self,
        provider: AIProvider | None = None,
        catalog: ToolCatalog | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._provider = provider or get_provider()
        self._catalog = catalog or get_catalog()
        self._settings = settings or get_settings()

    # ------------------------------------------------------------------ public
    def plan(self, message: str) -> tuple[SkillManifest, str]:
        """Return ``(manifest, explanation)`` for *message*."""
        message = (message or "").strip()
        if not message:
            raise ValueError("plan() requires a non-empty message")

        if self._provider.name == "mock":
            manifest, explanation = self._plan_mock(message)
        else:
            manifest, explanation = self._plan_with_llm(message)

        # Always stamp provenance.
        manifest.ai = SkillAI(
            generated_by="skillforge",
            planner_model=self._settings.model or self._provider.name,
            created_at=datetime.now(timezone.utc),
        )
        return manifest, explanation

    # ------------------------------------------------------------------ mock
    def _plan_mock(self, message: str) -> tuple[SkillManifest, str]:
        domain_key = self._catalog.find_domain(message) or "backend"
        label = self._catalog.domain_label(domain_key)

        # Tools mentioned explicitly in the message take priority.
        mentioned = self._catalog.find_tools_in_text(message)
        mentioned_names = {name for name, _ in mentioned}

        # Then fill from the catalog's recommended defaults for the domain.
        recommended: list[Tool] = []
        seen: set[str] = set()
        # First, the explicitly mentioned tools.
        for name, category in mentioned:
            if name in seen:
                continue
            seen.add(name)
            recommended.append(
                Tool(name=name, category=category, enabled=True, reason=_reason_for(name, category))
            )
        # Then top-of-list defaults — ONE tool per category — until we have a
        # useful stack. Taking only the first not-yet-seen tool per category
        # keeps recommendations focused and specific.
        for category in self._catalog.categories(domain_key):
            if len(recommended) >= 8:
                break
            for name in self._catalog.tools_for(domain_key, category):
                if name in seen:
                    continue
                seen.add(name)
                recommended.append(
                    Tool(name=name, category=category, enabled=True, reason=_reason_for(name, category))
                )
                break  # one tool per category

        # Ensure at least a language is present.
        if not any(t.category in {"languages", "language"} for t in recommended):
            for name, category in self._catalog.find_tools_in_text(message + " python go typescript"):
                if "language" in category:
                    recommended.insert(
                        0, Tool(name=name, category=category, enabled=True, reason=_reason_for(name, category))
                    )
                    break

        skill_name = self._derive_skill_name(message, domain_key, recommended)

        manifest = SkillManifest(
            schema_version="1.0",
            skill=SkillMeta(
                name=skill_name,
                title=_title_case(skill_name),
                domain=label,
                description=_summarize(message, label),
                version="0.1.0",
                status="draft",
            ),
            tools=recommended,
            architecture=Architecture(patterns=self.DEFAULT_PATTERNS.get(domain_key, ["Clean Architecture"])),
            workflow=list(self.DEFAULT_WORKFLOW.get(domain_key, ["Clarify requirements.", "Implement.", "Test."])),
            best_practices=list(self.DEFAULT_BEST_PRACTICES),
            output_standards=list(self.DEFAULT_OUTPUT_STANDARDS),
            outputs=Outputs(),
            safety=Safety(),
            example_prompts=_example_prompts(message, label),
            example_outputs=[
                "A concise explanation of the chosen stack and the rationale per tool.",
                "Runnable, well-structured code templates that follow the workflow.",
            ],
        )

        explanation = self._explain(label, recommended, domain_key)
        return manifest, explanation

    # ------------------------------------------------------------------ llm
    def _plan_with_llm(self, message: str) -> tuple[SkillManifest, str]:
        system_prompt = PLANNER_SYSTEM_PROMPT
        user_prompt = self._build_llm_user_prompt(message)
        raw = self._provider.complete_json(system_prompt, user_prompt)
        manifest = self._manifest_from_llm(raw, message)
        explanation = self._explain(manifest.skill.domain, manifest.tools, manifest.skill.name)
        return manifest, explanation

    def _build_llm_user_prompt(self, message: str) -> str:
        domain_hints = ", ".join(self._catalog.domain_keys())
        return PLANNER_USER_TEMPLATE.format(message=message, domains=domain_hints)

    def _manifest_from_llm(self, raw: Any, message: str) -> SkillManifest:
        if not isinstance(raw, dict):
            raise AIProviderError("Planner LLM did not return a JSON object")

        tools_raw = raw.get("recommended_tools") or raw.get("tools") or []
        tools: list[Tool] = []
        for t in tools_raw:
            if isinstance(t, dict):
                tools.append(
                    Tool(
                        name=str(t.get("name", "")).strip(),
                        category=str(t.get("category", "misc")).strip(),
                        enabled=bool(t.get("enabled", True)),
                        reason=str(t.get("reason", "")),
                    )
                )

        skill_name = str(raw.get("skill_name") or raw.get("name") or "").strip()
        skill_name = _sanitize_skill_name(skill_name) or self._derive_skill_name(message, "backend", tools)
        domain = str(raw.get("domain") or "").strip() or self._catalog.domain_label(
            self._catalog.find_domain(message) or "backend"
        )

        meta = SkillMeta(
            name=skill_name,
            title=str(raw.get("title") or _title_case(skill_name)),
            domain=domain,
            description=str(raw.get("summary") or raw.get("description") or _summarize(message, domain)),
            version="0.1.0",
            status="draft",
        )
        arch_patterns = raw.get("architecture_patterns") or (
            raw.get("architecture", {}) or {}
        ).get("patterns") or []
        return SkillManifest(
            schema_version="1.0",
            skill=meta,
            tools=tools,
            architecture=Architecture(patterns=[str(p) for p in arch_patterns]),
            workflow=[str(w) for w in (raw.get("workflow") or [])],
            best_practices=[str(b) for b in (raw.get("best_practices") or [])],
            output_standards=[str(o) for o in (raw.get("output_standards") or [])],
            outputs=Outputs(
                required_files=[str(f) for f in (raw.get("files_to_generate") or ["SKILL.md", "README.md", "config.yaml"])],
                required_directories=[str(d) for d in (raw.get("directories_to_generate") or ["prompts", "templates", "scripts", "examples"])],
            ),
            safety=Safety(),
            example_prompts=[str(p) for p in (raw.get("example_prompts") or _example_prompts(message, domain))],
            example_outputs=[str(o) for o in (raw.get("example_outputs") or [])],
        )

    # ------------------------------------------------------------------ utils
    def _derive_skill_name(self, message: str, domain_key: str, tools: list[Tool]) -> str:
        # Build "<domain>-<primary_framework_or_tool>-<secondary_tool>".
        tool_slugs: list[str] = []
        # Prefer framework-like categories first.
        priority_categories = (
            "frameworks",
            "framework",
            "orchestration",
            "vector_databases",
            "transformation",
            "databases",
            "database",
            "warehouses",
            "package",
            "iac",
        )
        chosen: list[str] = []
        for cat in priority_categories:
            if len(chosen) >= 2:
                break
            # Take the FIRST tool in this category, then move on so the name
            # reflects two distinct categories (e.g. framework + database).
            for t in tools:
                if t.category == cat and t.name not in chosen:
                    chosen.append(t.name)
                    break
        # Fall back to first two tools if no priority match.
        if not chosen:
            for t in tools[:2]:
                chosen.append(t.name)

        domain_slug = _slugify_domain(domain_key)
        for name in chosen:
            slug = _slugify_tool(name)
            if slug and slug not in tool_slugs:
                tool_slugs.append(slug)

        base = "-".join([domain_slug, *tool_slugs]) if tool_slugs else domain_slug
        base = base.strip("-")
        return _sanitize_skill_name(base) or "skill"

    def _explain(self, domain_label: str, tools: list[Tool], domain_key_or_name: str = "") -> str:
        lines = [f"Recommended domain: **{domain_label}**."]
        if tools:
            lines.append("Selected tools and why:")
            for t in tools[:8]:
                reason = t.reason or _reason_for(t.name, t.category)
                lines.append(f"- **{t.name}** ({t.category}): {reason}")
        lines.append(
            "These choices drive the generated workflow, best practices, templates, "
            "and validation rules. Edit the manifest to add, remove, or disable tools."
        )
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# Naming / slug helpers (module-level so tests can import them)
# ----------------------------------------------------------------------------


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify_tool(name: str) -> str:
    s = (name or "").lower()
    # Collapse compound provider names ("OpenAI-compatible API" → "openai").
    s = re.sub(r"\bapi\b", "", s)
    s = re.sub(r"\bcompatible\b", "", s)
    s = _SLUG_RE.sub("-", s).strip("-")
    return s


def _slugify_domain(key: str) -> str:
    s = (key or "").lower()
    s = s.replace("_", "-")
    s = _SLUG_RE.sub("-", s).strip("-")
    # Shorten long domain keys for readable skill names.
    return {
        "backend": "backend",
        "data-engineering": "data",
        "devops": "devops",
        "ai-engineering": "ai",
        "testing-qa": "testing",
        "observability": "observability",
        "web-scraping": "scraping",
        "frontend": "frontend",
    }.get(s, s)


def _title_case(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-")) + " Skill"


def _summarize(message: str, domain_label: str) -> str:
    snippet = message.strip().splitlines()[0] if message.strip() else ""
    if len(snippet) > 140:
        snippet = snippet[:137].rstrip() + "..."
    if not snippet:
        snippet = f"a {domain_label.lower()} skill"
    return f"Helps engineers with {domain_label.lower()} work. Based on: \"{snippet}\""


def _example_prompts(message: str, domain_label: str) -> list[str]:
    base = message.strip().splitlines()[0] if message.strip() else ""
    return [
        f"Help me start a new {domain_label.lower()} project matching this need.",
        f"Review my existing {domain_label.lower()} setup against these best practices.",
        f"Generate starter templates for the recommended {domain_label.lower()} stack.",
        base or f"Walk me through the recommended {domain_label.lower()} workflow.",
    ]


_NAME_RE = re.compile(r"^[a-z][a-z0-9]+(?:-[a-z0-9]+)+$")


def _sanitize_skill_name(name: str) -> str:
    name = (name or "").lower().strip()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^a-z0-9-]", "", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name


def _reason_for(name: str, category: str) -> str:
    name_l = (name or "").lower()
    table = {
        "python": "Strong ecosystem for backend, data, and AI engineering with great tooling.",
        "go": "Excellent for high-performance services and CLI tooling.",
        "typescript": "Type-safe language for frontend and Node backends.",
        "fastapi": "Modern async Python API framework with automatic OpenAPI docs.",
        "django": "Batteries-included Python web framework for content and admin apps.",
        "flask": "Lightweight Python web framework for small services.",
        "postgres": "Reliable relational database for production workloads.",
        "postgresql": "Reliable relational database for production workloads.",
        "sqlalchemy": "Mature Python ORM and SQL toolkit.",
        "sqlmodel": "Pydantic + SQLAlchemy ORM with strong typing.",
        "alembic": "Standard migration tool for SQLAlchemy projects.",
        "pytest": "Simple, powerful Python testing framework.",
        "docker": "Standard packaging and reproducible local environments.",
        "github actions": "OSS-friendly CI/CD with hosted runners.",
        "opentelemetry": "Vendor-neutral tracing, metrics, and logs instrumentation.",
        "airflow": "Battle-tested DAG-based data orchestrator.",
        "dagster": "Asset-centric data orchestrator with strong typing.",
        "dbt": "SQL transformation framework with tests and documentation.",
        "bigquery": "Serverless, scalable data warehouse.",
        "snowflake": "Managed cloud data warehouse.",
        "kafka": "Distributed event streaming platform.",
        "kubernetes": "Container orchestration standard.",
        "helm": "Package manager for Kubernetes applications.",
        "terraform": "Declarative infrastructure-as-code tool.",
        "langchain": "Composable framework for LLM applications.",
        "llamaindex": "Data framework for RAG and retrieval pipelines.",
        "pgvector": "Vector storage inside PostgreSQL.",
        "qdrant": "Production-ready vector search engine.",
        "playwright": "Reliable browser automation for e2e and scraping.",
        "scrapy": "Fast, extensible web scraping framework.",
        "prometheus": "Metrics collection and alerting toolkit.",
        "grafana": "Dashboards and visualization for metrics and logs.",
        "loki": "Horizontally scalable log aggregation system.",
        "next.js": "React framework with SSR/SSG and API routes.",
        "react": "Component-based UI library.",
        "tailwind css": "Utility-first CSS framework.",
        "shadcn/ui": "Accessible, copy-paste React component collection.",
    }
    return table.get(name_l) or f"Recommended {category} tool for this skill's stack."


# ----------------------------------------------------------------------------
# LLM prompts
# ----------------------------------------------------------------------------


PLANNER_SYSTEM_PROMPT = """You are SkillForge's engineering skill planner.

Given a natural-language engineering need, you produce a JSON object describing a
SPECIFIC, tool-driven skill. Never produce a generic skill name such as
"backend", "frontend", "fullstack", or "data". The skill name MUST be kebab-case
and include the primary tool(s), e.g. "backend-fastapi-postgres",
"data-airflow-dbt-bigquery", "ai-rag-langchain-pgvector".

You MUST return ONLY a JSON object with this exact shape:

{
  "skill_name": "kebab-case-specific-name",
  "title": "Human-readable Title",
  "domain": "Domain Engineering",
  "summary": "One or two sentences describing the skill.",
  "recommended_tools": [
    {"name": "Tool", "category": "framework", "reason": "why this tool fits"}
  ],
  "architecture_patterns": ["Pattern One", "Pattern Two"],
  "workflow": ["Step 1", "Step 2"],
  "best_practices": ["Practice 1", "Practice 2"],
  "output_standards": ["Standard 1"],
  "files_to_generate": ["SKILL.md", "README.md", "config.yaml"],
  "directories_to_generate": ["prompts", "templates", "scripts", "examples"],
  "example_prompts": ["A realistic user prompt"],
  "example_outputs": ["A realistic output description"]
}

Rules:
- Recommend at least 3 and at most 9 specific tools.
- Each tool must have a concrete reason tied to the user's need.
- The workflow must reference the chosen tools.
- Do not invent libraries that do not exist. Prefer mainstream, mature tools.
- Output JSON only. No prose, no code fences.
"""


PLANNER_USER_TEMPLATE = """Engineering need:
\"\"\"
{message}
\"\"\"

Known domains in the catalog: {domains}.

Produce the skill-planning JSON now."""


# ----------------------------------------------------------------------------
# Convenience
# ----------------------------------------------------------------------------


def plan_skill(message: str, planner: "AISkillPlanner | None" = None) -> tuple[SkillManifest, str]:
    """Plan a skill from *message* using the configured provider."""
    return (planner or AISkillPlanner()).plan(message)


# Kept for parity with the (optional) JSON export used by some callers.
def manifest_to_jsonable(manifest: SkillManifest) -> dict[str, Any]:
    return json.loads(manifest.model_dump_json())
