# Contributing to SkillForge

Thanks for your interest in contributing! SkillForge is local-first and open-source, and we want contributions to be easy and safe.

## Code of Conduct

Participation in this project is governed by the [Code of Conduct](./CODE_OF_CONDUCT.md). Please be excellent to each other.

## Ways to contribute

- **Tools & domains** — extend [`apps/api/skillforge_api/data/tool_catalog.yaml`](./apps/api/skillforge_api/data/tool_catalog.yaml) with new domains or tools. This is the easiest way to make SkillForge smarter.
- **Templates** — improve the Jinja2 templates in [`apps/api/skillforge_api/templates/`](./apps/api/skillforge_api/templates/).
- **Example skills** — add new example skills under [`examples/`](./examples/).
- **Bug fixes & features** — see [Issues](#) and [`docs/roadmap.md`](./docs/roadmap.md).
- **Docs** — clearer docs are always welcome.

## Development setup

See the [Development setup](./README.md#development-setup) section of the README. In short:

```bash
cd apps/api && pip install -e ".[dev]"
cd ../cli  && pip install -e .
cd ../web  && npm install
```

## Workflow

1. Fork and create a feature branch from `main` (e.g. `feat/add-go-tools`).
2. Make your change with focused commits. Match existing code style.
3. Add or update tests where relevant.
4. Run the test suite:

   ```bash
   cd apps/api && pytest -q
   ```

5. For Web UI changes, run `npm run build` to confirm it compiles.
6. Open a pull request describing **what** changed and **why**.

## Commit messages

Use Conventional Commits:

```
feat(planner): recommend Alembic when SQLAlchemy is selected
fix(installer): reject generic skill names
docs(readme): clarify provider configuration
chore(deps): bump pydantic to 2.7
```

## Safety expectations

SkillForge is safe-by-default. Contributions **must** preserve these invariants:

- Never auto-execute generated scripts or shell commands.
- Never install a skill without an explicit user action.
- Never overwrite an installed skill unless `overwrite` is explicitly set.
- Never send local files to an AI provider unless the user explicitly provides them.
- Secrets come only from environment variables.

PRs that violate these will be rejected.

## Adding a new tool to the catalog

```yaml
domains:
  my_domain:
    label: My Domain
    recommended_tools:
      languages:
        - Python
      frameworks:
        - MyFramework
```

Then add a test in [`apps/api/tests/test_tool_catalog.py`](./apps/api/tests/test_tool_catalog.py) if you introduce a new category.

## Reporting security issues

Please do **not** open a public issue for security problems. See the security policy in the README. SkillForge runs entirely locally and never auto-executes generated code, but please report any issue that could break that contract.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
