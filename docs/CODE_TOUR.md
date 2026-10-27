# Source tour

## Patch Audit in five minutes

Follow one evidence object across these boundaries:

1. [RepositoryAudit.tsx](../frontend/src/RepositoryAudit.tsx) and
   [IndependentPlan.tsx](../frontend/src/IndependentPlan.tsx): guided input, exact approvals,
   response-selection guards and separate result presentation.
2. [intake.py](../backend/src/workbench/repository_audit/intake.py) and
   [admission.py](../backend/src/workbench/repository_audit/admission.py): immutable Git tree/blob
   validation and exact production-only patch application. The separate
   [PR preview](../backend/src/workbench/repository_audit/github_preview.py) creates no admitted data.
3. [verification.py](../backend/src/workbench/repository_audit/verification.py) and
   [independent.py](../backend/src/workbench/repository_audit/independent.py): requirement provenance,
   versioned plans, control validation and expected-versus-observed interpretation.
4. [execution.py](../backend/src/workbench/repository_audit/execution.py) and
   [service.py](../backend/src/workbench/repository_audit/service.py): restricted container execution,
   persisted transitions, full evidence binding and idempotent reconciliation. Inspect
   [recovery.py](../backend/src/workbench/repository_audit/recovery.py) for bounded lifecycle diagnostics.
5. [release.py](../backend/src/workbench/release.py) and
   [release.Dockerfile](../docker/release.Dockerfile): the physically separate recorded-only surface.
   [G4 browser acceptance](../backend/tests/test_g4_browser.py) exercises the complete local journey;
   [recovery regressions](../backend/tests/test_repository_recovery_deadlines.py) exercise failures.

[Actual G4 evidence and limits](reports/GENERALIZED-PATCH-AUDIT-G04.md) ·
[First audit](PATCH-AUDIT-QUICKSTART.md) · [Trust-boundary diagram](ARCHITECTURE.md#patch-audit-trust-boundaries)

## Earlier debugger and repair workflows

| Start here | Responsibility |
| --- | --- |
| [frontend/src/main.tsx](../frontend/src/main.tsx), [Workflow.tsx](../frontend/src/Workflow.tsx) | Scenario selection, complete journey and separate stage status |
| [Investigation.tsx](../frontend/src/Investigation.tsx) | Structured diagnosis, saved inputs, clickable citations and Retrieval Inspector |
| [Repair.tsx](../frontend/src/Repair.tsx), [Diff.tsx](../frontend/src/Diff.tsx) | Identity-bound repair actions, results, exact diff and editor lifecycle |
| [RemotePreview.tsx](../frontend/src/RemotePreview.tsx) | Trusted controls and pixels; no visitor-side generated script |
| [api.py](../backend/src/workbench/api.py), [access.py](../backend/src/workbench/access.py) | HTTP boundary, session ownership and persisted quota reservations |
| [runner.py](../backend/src/workbench/runner.py) | Fixed trusted Playwright reproduction; no inference secret or generated patch |
| [rag/snapshot.py](../backend/src/workbench/rag/snapshot.py), [retrieval.py](../backend/src/workbench/rag/retrieval.py) | Frozen source validation, chunking, pgvector/FTS fusion and reranking |
| [rag/provider.py](../backend/src/workbench/rag/provider.py), [diagnosis.py](../backend/src/workbench/rag/diagnosis.py) | Real replaceable NVIDIA adapter and validated source-grounded output |
| [repair/graph.py](../backend/src/workbench/repair/graph.py), [service.py](../backend/src/workbench/repair/service.py) | Bounded LangGraph repair, native checkpoints, task lifecycle and retained failures |
| [mcp_client.py](../backend/src/workbench/repair/mcp_client.py), [mcp_server.py](../backend/src/workbench/repair/mcp_server.py) | Actual official-SDK discovery/calls, approved source and candidate tools |
| [broker.py](../backend/src/workbench/repair/broker.py), [verifier.py](../backend/src/workbench/repair/verifier.py) | Private Docker authority, actual byte/image identity, independent checks and remote preview |
| [release.py](../backend/src/workbench/release.py), [Recorded.tsx](../frontend/src/Recorded.tsx) | Separate immutable recorded release surface |
| [evaluate_repairs.py](../scripts/evaluate_repairs.py), [evals](../evals/README.md) | Frozen comparison, pre-request budget ledger and sealed final scoring |

Target source uses canonical `fixtures/retail/*` paths. Variant manifests map `cart.js` to its committed `fixtures/scenarios/<id>/cart.js` origin. Citations resolve against saved source bytes, not the working tree. Target source is separate from trusted verifiers, offline controls and evaluation-only checks.
