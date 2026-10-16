# Roadmap

1. **Functional product foundation** — retail fixture, real Playwright reproduction, PostgreSQL history, browser evidence and interactive workspace. Accepted for its local, trusted-fixture scope. Integrated through PR #1.
2. **NVIDIA AI + advanced RAG** — live inference, commit-aware code indexing, hybrid retrieval, reranking, citations, retrieval inspector and baseline evaluation. Accepted for its local, approved-snapshot diagnosis scope. Integrated through PR #2.
3. **MCP + autonomous repair + verification** — stateful LangGraph execution, real MCP tools, bounded isolated patches, diff, trusted verification, budgets and cancellation. Accepted for the bounded local scope at `0c2dc0348d1b0b3f961466f214884e53c21bc14d`; integrated through PR #3.
4. **Evaluation + UX + release readiness** — held-out evaluation, ablations, latency/cost, accessibility, security, recorded fallback, deployment preparation and video. Accepted and integrated through PR #4, including the guest-authorization correction at `d43d816`: twelve frozen scenarios, limited evaluation, remote pixel previews, recorded release and tested activation preparation.

All four milestones are accepted and integrated into `main` using history-preserving merge commits. The owner authorized v1.0.0 repository publication; application hosting remains inactive and requires separate authorization. Historical reports retain their review-time status.

## Backlog

Broader independently sourced defects and hosted execution require separate scope and isolation review. Keep the supported scenario boundary explicit.

Retain lexical and whole-target baselines: this corpus is small enough that additional retrieval complexity did not establish a diagnosis advantage. The frozen Milestone 4 comparison also found no resolution advantage over whole-target input on this small suite.

Release backlog: broader independently sourced defects; public live execution only after a separate isolation/hosting authorization; smaller Monaco bundle if measured UX warrants it. No additional formal milestone is created.
