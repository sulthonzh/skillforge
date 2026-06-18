## Summary
<!-- One or two sentences: what does this PR change? -->

## Type of change
<!-- Check all that apply -->
- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (fix or feature that changes existing behavior)
- [ ] Documentation
- [ ] Refactor / cleanup

## Checklist
- [ ] `pytest -q` passes in `apps/api`
- [ ] `ruff check apps/api apps/cli` is clean
- [ ] `npx tsc --noEmit` passes in `apps/web` (if frontend touched)
- [ ] Tests added for new behavior
- [ ] `CHANGELOG.md` updated (if user-facing)
- [ ] No secrets / API keys committed

## Test plan
<!-- How did you verify this works? e.g. "ran eval on skill-creator, scored 9/10" -->
