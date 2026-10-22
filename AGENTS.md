# Project instructions

The four development milestones are accepted and integrated. Future work is maintenance within explicitly requested scope; no additional formal milestone is implied. Preserve accepted commits, review tags, source snapshots, reports and retained failures.

The owner authorized the one-time integration and publication of this repository for v1.0.0. That authorization does not grant blanket permission for future merges, releases, visibility changes or deployments. Public application hosting and live execution require separate explicit authorization.

Keep generated patches away from trusted tests, infrastructure, and secrets. Browser reproduction is a fixed, allowlisted procedure; arbitrary commands, target URLs, and repository paths must never be accepted from requests. Never claim AI inference or independent repair verification before those exist.

Use Python 3.12, typed async services, Pydantic contracts, SQLAlchemy and Alembic. Use React and TypeScript for the workspace. Keep money in integer cents. Persist run transitions and evidence. Represent infrastructure errors separately from a reproduced defect.

Run `./scripts/check` and `./scripts/e2e` for maintenance verification. Document actual results in `docs/reports/`. Never commit credentials, runtime artifacts, browser traces with secrets, or environment files. Commit only sanitized screenshots from the synthetic fixture or explicitly requested public G1 examples.

Prefer complete user journeys to additional infrastructure. Keep architecture and decisions concise. Additional ideas belong in the roadmap backlog.

Milestone 4 evaluation configuration is frozen in `evals/experiment-v2.json`. Do not tune against held-out outcomes or overwrite its results. A required engine/runtime/scoring change needs a new versioned experiment while retaining v1. Keep `evals/final_checks.py`, offline controls, reports and recordings outside runtime retrieval/MCP inputs.

Public release uses only `compose.release.yaml` / the recorded server. Do not expose the privileged live stack, send generated candidate scripts to visitor tabs, or enable public inference by changing a UI flag. Public activation still requires owner authorization.

The owner separately authorized the one-time accepted Patch Audit integration and v1.1.0
repository release, plus recorded-only deployment in the existing Vercel account. Preserve
M1/M2 freezes and failed readiness; M3 remains on hold. This grants no blanket permission
for future merges, releases, paid services, deployments or public candidate execution.

G1 is separately authorized: `repository_audit` may accept validated public GitHub
owner/repository identifiers, full immutable commits, production-only diffs and typed
local-owner-approved argv execution plans. This exception applies only to the new
local workflow. Repository content is untrusted, intake never executes it, all setup
and tests require restricted broker containers, and the recorded server must have
no generalized intake or execution authority. Do not change frozen historical inputs.

G2 is separately authorized on a branch stacked on accepted G1: versioned, independently
justified requirements and explicitly approved declarative Python/Node checks may extend
the local workflow. Candidate patches cannot modify checker material or expectations.
Validate named positive/negative controls before scoring; keep ordinary and independent
environments fresh and separate. No paid/live inference, public execution, deployment,
release, merge or G3 work is authorized. Preserve every historical G1/M1/M2 artifact.
