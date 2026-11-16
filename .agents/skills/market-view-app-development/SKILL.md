---
name: market-view-app-development
description: Implement market-view Python/FastAPI or React/TypeScript trading research UI features using existing contracts, charts, and project-specific verification.
---

# Develop the application

Inspect the affected source and actual dependency manifests first. Keep the modular monolith
and existing contracts; distinguish research/API/UI work from execution authority.

- Backend: reuse Pydantic contracts, settings, serializers, and job management. Slow research
  runs belong off the request path. Keep the locked holdout unavailable through the UI.
- Frontend: read `frontend/package.json` and component conventions. Reuse the current design
  system. Chart series need finite values and unique ascending times; daily timestamps must
  retain their NSE business date. Compute trading indicators with the backend's implementation.
- Show data source/as-of time, mode, costs, drawdown, sample size, rejection reasons, and job
  errors where they affect a decision. Do not label an unvalidated setup as an approved trade.
- Preserve local-only API assumptions unless deployment/authentication work is in scope.
  UI controls must not bypass risk checks or silently turn research into order placement.
- Run meaningful checks for the actual change. Do not add tests that merely mirror wording.

Read only relevant existing references:

| Work | Local reference |
| --- | --- |
| Python | `../../../.claude/skills/python-pro/SKILL.md` |
| FastAPI/Pydantic | `../../../.claude/skills/fastapi-expert/SKILL.md` |
| Dataframes | `../../../.claude/skills/pandas-pro/SKILL.md` |
| React | `../../../.claude/skills/react-expert/SKILL.md` |
| TypeScript | `../../../.claude/skills/typescript-pro/SKILL.md` |
| Trading charts | `../../../.claude/skills/lightweight-charts/SKILL.md` |
| Existing shadcn components | `../../../.claude/skills/shadcn/SKILL.md` |
| Debugging | `../../../.claude/skills/systematic-debugging/SKILL.md` |

For browser verification use the installed `playwright` skill when appropriate. Its package
is project-local: resolve scripts beneath `.agents/skills/playwright/`, not a presumed global
installation. On Windows use the actual shell or the equivalent npx command. Install browser
runtime dependencies only when the requested browser task needs them.

Postgres, Rust, broad MLOps stacks, and dependency replacements need a demonstrated task need;
they are not prerequisites inherited from generic examples.
