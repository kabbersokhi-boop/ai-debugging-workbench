# Roadmap

1. **Functional product foundation** — retail fixture, real Playwright reproduction, PostgreSQL history, browser evidence and interactive workspace. Accepted for its local, trusted-fixture scope. PR #1 remains unmerged.
2. **NVIDIA AI + advanced RAG** — live inference, commit-aware code indexing, hybrid retrieval, reranking, citations, retrieval inspector and baseline evaluation. Implemented; awaiting milestone 2 review.
3. **MCP + autonomous repair + verification** — stateful LangGraph execution, real MCP tools, bounded isolated patches, diff, trusted verification, budgets and cancellation. Requires milestone 2 approval.
4. **Evaluation + UX + release readiness** — held-out evaluation, ablations, latency/cost, accessibility, security, recorded fallback, deployment preparation and video. Requires milestone 3 approval.

No milestone PR is merged automatically. Public release requires explicit approval.

## Backlog

Add defects only when needed to evaluate retrieval and repair. Multi-user authentication, durable distributed execution, and hosted sandbox orchestration are deployment decisions for milestone 4; do not expand the local foundation into a platform.

Retain lexical and whole-target baselines: this corpus is small enough that additional retrieval complexity did not establish a diagnosis advantage. Broader evaluation belongs to milestone 4.
