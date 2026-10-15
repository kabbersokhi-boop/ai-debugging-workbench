# Project instructions

Build one reviewable milestone at a time. Do not merge milestone PRs, start the next milestone, publish the repository, or deploy publicly without user approval.

Keep generated patches away from trusted tests, infrastructure, and secrets. Browser reproduction is a fixed, allowlisted procedure; arbitrary commands, target URLs, and repository paths must never be accepted from requests. Never claim AI inference or independent repair verification before those exist.

Use Python 3.12, typed async services, Pydantic contracts, SQLAlchemy and Alembic. Use React and TypeScript for the workspace. Keep money in integer cents. Persist run transitions and evidence. Represent infrastructure errors separately from a reproduced defect.

Run `./scripts/check` and `./scripts/e2e` for milestone acceptance. Document actual results in `docs/reports/`. Never commit credentials, runtime artifacts, browser traces with secrets, or environment files. Commit only sanitized screenshots from the synthetic fixture.

Prefer complete user journeys to additional infrastructure. Keep architecture and decisions concise. Additional ideas belong in the roadmap backlog.

Milestone 4 evaluation configuration is frozen in `evals/experiment-v2.json`. Do not tune against held-out outcomes or overwrite its results. A required engine/runtime/scoring change needs a new versioned experiment while retaining v1. Keep `evals/final_checks.py`, offline controls, reports and recordings outside runtime retrieval/MCP inputs.

Public release uses only `compose.release.yaml` / the recorded server. Do not expose the privileged live stack, send generated candidate scripts to visitor tabs, or enable public inference by changing a UI flag. Public activation still requires owner authorization.
