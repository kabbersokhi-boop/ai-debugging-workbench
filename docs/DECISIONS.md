# Decisions

## 001 — Ship browser proof before agent infrastructure

Build one curated cart defect end to end. A real browser with inspectable screenshots, a passing control, and failing pricing assertions proves the product foundation. NVIDIA, LangGraph, MCP, vector indexing, and Monaco arrive in milestones 2–3 when their behavior can be demonstrated. No deterministic response is presented as model output.

## 002 — Separate browser execution from the API

Use a small HTTP runner with a fixed recipe and structured streaming events. The runner has no database credentials or arbitrary execution surface. This establishes an execution boundary now without pretending a container running trusted code is a sufficient sandbox for future generated patches.

## 003 — PostgreSQL is the source of truth; retain a single coordinator

Commit each event with its associated state transition. Use a managed task registry and admission limit for local execution; a database advisory lock rejects a second coordinator. Recovery labels interrupted work honestly. This delivers cancellation and durable evidence without introducing Redis or a distributed task queue. Durable resumption is deferred.

## 004 — Poll committed evidence

Stream runner events to the API over NDJSON and poll the database-backed API in the browser. At this workload, 650 ms polling offers straightforward reconnection and refresh behavior. WebSockets would not improve correctness or the acceptance criterion. This is reversible if later measured latency justifies streaming to clients.

## 005 — Establish a control before attributing a defect

Validate one-item pricing before changing quantity. Require the exact reported mismatch to classify reproduction. Other mismatches and failed browser actions are errors, not manufactured defect confirmations. Fixed expected values live outside the defective source. Unit tests include correct behavior as a negative control; integration tests exercise unavailable, invalid, empty and timed-out runner responses.

## 006 — Keep source visual assets simple

Use a restrained developer workspace, accessible Radix tabs, a responsive layout, and an interactive retail fixture. The daypack illustration is CSS native. No bitmap generation, external fonts, or asset network requests are required. Screenshots in the application are real Playwright captures.

## 007 — Protect browser cleanup from disconnect cancellation

A real API process crash exposed a Playwright transport `InvalidStateError` during ASGI disconnect cleanup. AnyIO cancellation can recur at every await. Shield driver startup and browser/driver teardown from that cancellation while allowing recipe execution to cancel normally. Regression tests check cleanup after cancellation and failed launch; the Compose crash check proves interrupted status, retained history, a successful new run, and no runner cleanup traceback. This follows [AnyIO's documented finalization guidance](https://anyio.readthedocs.io/en/stable/cancellation.html#finalization).


## 008 — Freeze a target-only source snapshot and persist its bytes

The runtime indexes exactly four explicitly allowed retail source/developer files from an immutable commit. Store source bytes and line-grounded chunks with snapshot identity; never resolve historical citations against latest files. Refuse mismatched reproduction digests. Reformatting the fixture improves source inspection without fixing its defect. Reports, trusted tests, evaluation labels and reference fixes remain outside the corpus.

## 009 — Extend PostgreSQL in place

Compile pgvector 0.8.7 onto the same PostgreSQL 17 Alpine image family and reuse the original volume. Backup and verify original run IDs and reviewed artifact hashes. Additive Alembic migrations preserve Milestone 1 tables; downgrade checks use a disposable database. Exact vector search is appropriate for 84 chunks; ANN would add complexity without measured need.

## 010 — Keep provider controls explicit and orchestration small

Use an async NVIDIA transport adapter plus LangChain Core prompt/runnable/Pydantic parsing. The existing coordinator owns bounded diagnosis tasks; LangGraph and MCP remain milestone 3. A small real comparison favored Nemotron 3.5 Super over Lightning for precise cause attribution. Current Nemotron embeddings and native VL reranking passed actual calls; several older documented endpoints were retired. No hardcoded diagnosis, silent fallback or output repair is used.

## 011 — Preserve unfavorable evaluation results

On this four-file target, lexical retrieval had better recall than dense/hybrid variants, and whole-target diagnosis was competitive with RAG. Retain the required inspectable hybrid pipeline and simpler baselines without claiming a superiority that was not measured. An out-of-range no-answer citation was rejected instead of clipped into a valid range. Future evaluation can justify simplification or a different default; eight queries over one defect cannot establish general debugging accuracy.
