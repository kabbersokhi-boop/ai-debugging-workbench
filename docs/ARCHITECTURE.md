# Architecture — milestones 1–3

One complete path: select a supported report → launch real Chromium → establish a passing baseline → change cart quantity → capture screenshots and DOM observations → compare a trusted contract → persist the outcome.

```mermaid
flowchart LR
  Visitor[React workspace] -->|HTTP / polling| API[FastAPI coordinator]
  API -->|Transactions| DB[(PostgreSQL)]
  API -->|Fixed recipe / NDJSON events| Runner[Browser runner]
  Runner --> Chromium[Fresh Chromium context]
  Chromium --> Fixture[Local retail fixture]
  Runner -->|Writes| Evidence[(Artifact volume)]
  Evidence -->|Read only| API
```

## Runtime boundaries

The **API** validates the only supported bug ID, applies idempotency keys, limits admission to two active runs, and commits ordered events and terminal outcomes. One coordinator is enforced with a PostgreSQL advisory lock. The API calls a separate runner over HTTP; it never executes submitted commands. The frontend polls persisted state every 650 ms while active, with connection errors and retry feedback. History survives refreshes and API restarts.

The **runner** accepts a UUID for a fixed recipe. It receives no database or inference credentials. Its container has a read-only root filesystem, an artifact volume, temporary storage, memory/PID limits, no added capabilities and no new privileges. It belongs only to an internal Docker network. Browser routing accepts only the local fixture origin and path. There is no caller-controlled URL, script, shell command, or repository path. The browser is Playwright's bundled Chromium; the runner image and Python package use the same version.

This is containment for a trusted recipe on a trusted synthetic fixture. Chromium uses Playwright's default launch arguments, including disabling its own sandbox. **This is not yet a sandbox for untrusted generated code.** Milestone 3 must provide that stronger execution boundary before accepting patches.

The **fixture** is a functional retail UI with add-to-bag and quantity controls, integer-cent pricing, shipping rules, and an intentionally defective subtotal calculation. It accepts no payments or customer data. The manual embedded storefront uses a separate browser session from automation; manipulating it cannot alter automated observations.

## Evidence and outcome contract

Every run has a UUID, supported report ID, timestamps, state, ordered events, optional error, and optional validated result. Each completed result contains baseline and after-action DOM observations, independent expected values, per-assertion comparisons, fixture SHA-256, Chromium version, elapsed time, screenshots, console capture, and a native Playwright trace. Expected pricing is defined in the trusted runner, separately from the storefront calculation. Monetary assertions use cents.

| State | Meaning |
| --- | --- |
| `queued` / `running` | Accepted / browser execution in progress |
| `reproduced` | Passing baseline, successful quantity action, and the exact reported mismatch observed |
| `not_reproduced` | Passing baseline and all after-action pricing assertions passed |
| `error` | Infrastructure, invalid evidence, unexpected mismatch, or timeout; no defect conclusion |
| `cancelled` | Cancellation accepted; incomplete execution has no result |
| `interrupted` | An unfinished run was found after an unclean API restart |

A failing application assertion is a successful **reproduction**, not a verified repair. NVIDIA diagnosis has its own persisted status and execution trail. A structured diagnosis with valid citations is a proposal, not independently established truth. Reproduction and diagnosis do not represent repair verification; milestone 3 stores repair states separately.

Events and status updates share database transactions and row locks. Terminal states cannot be overwritten by late responses. Duplicate idempotency keys return the original run. The API owns and awaits its execution tasks; shutdown cancels them. A 60-second overall budget and a 55-second runner budget bound execution. Restart recovery marks remaining active rows interrupted and retains their partial evidence. Run/artifact access is validated through persisted run identities and an artifact allowlist.

## Data and delivery

SQLAlchemy async sessions use PostgreSQL; Alembic owns schema changes. There is no SQLite fallback or in-memory substitute. The API serves the production React build and immutable fixture on one origin. Compose starts PostgreSQL, a one-shot migration, the runner, and the API in readiness order. The API and development database ports bind only to loopback. Local database credentials are explicitly disposable. There is no authentication or remote hosting yet.

The shared Playwright runtime image avoids maintaining different browser/library environments. The API does not launch the installed browser. A smaller API image is a deferred optimization; working isolation and one reproducible environment matter more at this stage.

## Grounded diagnosis (milestone 2)

A separate `InvestigationManager` extends the existing coordinator; there is no second orchestration engine or repair agent. It admits two investigations, bounds each to 180 seconds, preserves partial evidence, cancels provider work, and marks unfinished diagnoses interrupted after restart. It never changes reproduction status. Reports are bounded to 4,000 characters. Provider calls have a 45-second timeout, one bounded transient retry, a 12-request investigation limit, a conservative 32,768-token input bound and 1,400 output tokens. Rejected outputs are not silently rewritten or replaced.

`NvidiaProvider` is a replaceable async protocol implementation. LangChain Core composes the rendered chat prompt, async provider runnable and Pydantic output parser. The adapter owns transport, retries, response-envelope checks and measured usage. HTTP error bodies and authorization headers are excluded from traces. Runtime settings do not read secret files; only provider settings load the ignored backend credential configuration. Compose injects it into the API only. The runner image contains no environment file and receives no NVIDIA credentials.

### Immutable approved source

The corpus is exactly `fixtures/retail/{cart.js,index.html,styles.css,README.md}` at commit `b44dfbb5c6804638e42d2dcc76565aa8d12aeb2a`. Formatting makes source ranges readable; developer documentation describes normal product behavior without supplying a reference fix. There are four files, 13,983 UTF-8 bytes and 84 chunks. No workbench reports, trusted checks, evaluation labels, fixes, secrets or future commits are ingested. No target developer tests are approved or indexed in this version.

`scripts/freeze_corpus.py` reads only that allowlist from an explicit Git commit and packages source bytes and hashes. Snapshot identity incorporates the commit and file hashes; the fixture digest matches the reproduction runner's file-digest algorithm. The API refuses to investigate a reproduction from another source digest. Older reproduction history and artifacts remain intact; rerun reproduction to investigate the new snapshot.

PostgreSQL stores the entire immutable manifest, source bytes, model-specific index and chunks. Unchanged indexing returns the existing index without new embedding calls; an advisory transaction lock also serializes concurrent initial indexing. A failed initial embedding operation rolls back the incomplete index. Retrieval rejects a mismatched snapshot or embedding model before querying chunks.

### Actual retrieval and context

JavaScript uses Tree-sitter function/top-level boundaries, documentation uses headings, HTML uses section boundaries, and CSS uses rule boundaries. Larger blocks split at line boundaries. PostgreSQL full-text retrieval uses stemming, code-name normalization and `ts_rank_cd`; pgvector performs exact cosine retrieval. Rank lists fuse with reciprocal rank fusion (k=60), then the native NVIDIA reranker orders at most 12 candidates. No ANN index is needed for 84 chunks. The extension is compiled onto the same PostgreSQL 17 Alpine base, retaining the existing data volume and locale family.

Context selection includes complete chunks in rank order within a 4,000-unit budget, counting UTF-8 bytes as a conservative token bound rather than claiming an exact NVIDIA tokenizer count. Source headers, line numbering and separators count toward that bound. Exact selected snippets, candidates, ranks, scores, selection reasons, query, rendered prompt, report, observations and provider calls are persisted. The Retrieval Inspector distinguishes candidates from supplied context. Citation buttons open the persisted source snippet, never the latest working tree.

The model receives report, browser observations and repository context as distinct inputs. Pydantic validates diagnosis/insufficient-evidence structure. Citation checks require supplied source IDs and inclusive ranges within those supplied chunks; the server binds each accepted citation to its frozen path, snapshot and commit. These checks do not verify the reasoning. Out-of-context citations are an explicit invalid-output outcome.

### Evaluation boundary

The frozen eight-query smoke suite is outside the ingestion allowlist. It covers one defect, supporting behaviors and two no-answer questions; paraphrases are not counted as new defects. Live lexical, dense, hybrid and reranked results are retained. A same-model comparison supplies either retrieved chunks or the whole four-file target. Measured results favor simpler lexical retrieval for recall on this corpus; no general RAG benefit or debugging success rate is claimed. Dollar cost is unavailable; reported token counts come from provider responses. See the milestone 2 report.

## Bounded repair (milestone 3)

```mermaid
flowchart LR
  UI[Existing investigation + Monaco diff] --> API
  API --> Graph[Typed LangGraph + NVIDIA decisions]
  Graph --> Checkpoints[(PostgreSQL native checkpoints)]
  Graph -->|Official SDK / JSON-RPC stdio| MCP[Run-bound source and candidate tools]
  MCP --> Broker[Trusted Docker broker / external verifier]
  Broker --> Candidate[Disposable static target + Chromium]
  UI -->|Separate origin / opaque sandbox iframe| Preview[Preview gateway :8013]
```

The repair graph loads immutable reproduction/diagnosis inputs, lets the model choose bounded source reads/searches, validates a model-produced exact-text patch, creates a candidate through MCP, requests trusted verification, and permits one revision after a rejected patch or failed behavioral checks. The only allowed changed path is `fixtures/retail/cart.js`. There is no reference fix or generated test in runtime prompts. The original fixture and source snapshot are untouched.

`RepairState` records identities, source evidence, exact prompts and sanitized model responses, candidate attempts/hashes, verifier evidence, errors, deadline and remaining request/output budgets. The native LangGraph `AsyncPostgresSaver` saves intermediate node state, blobs and pending writes in the `repair_graph` schema. Alembic revision 004 adds those SDK tables and repair history without resetting existing volumes. Reproduction, diagnosis and repair have independent statuses.

One API repair is admitted at a time. The shared budget is eight provider HTTP requests including transient retries, at most six model decisions, two proposed patches, 2,000 output tokens per request and 16,000 reserved output tokens across the run. Maximum output is charged even for failed requests/retries. The 300-second deadline starts at admission and includes source reads, inference, candidate startup and verification. Individual provider requests retain their 45-second timeout. MCP source reads are at most 80 lines, with at most six read/search calls. No node replenishes resources.

MCP uses the official Python SDK (locked 1.30.0), real discovery and stdio client/server communication. Each server subprocess is launched with a trusted repair UUID, frozen snapshot identity and broker address; it receives no NVIDIA/database environment. Model arguments cannot choose a run, broker URL, command, repository root or verifier suite. The four tools are `search_source`, `read_source`, `apply_candidate` and `verify_candidate`. A Pydantic decision loop drives source tools and patch proposals. Actual discovery, arguments, results and rejected calls are retained. Infrastructure failures remain execution errors, distinct from invalid patches.

### Candidate and verifier isolation

The fixed reproduction runner is unchanged. Only the dedicated trusted broker has the Docker socket; neither the API, MCP child, candidate nor reproduction runner mounts it. The broker contains no provider/database credentials. **The broker itself has Docker/host authority and is trusted infrastructure**, not a sandboxed agent tool executor. Its control listener binds only to its management network address; the candidate-side interface has no control listener. A separate GET-only preview listener is published to loopback port 8013.

Each attempt has its own internal Docker network, initialized source volume and disposable container. The candidate image contains a static HTTP server and Chromium, not the workbench, trusted verifier, secret configuration or tests. Source is mounted read-only; the root filesystem is read-only. Limits are 1 CPU, 1 GiB memory, 192 processes, 256 MiB temporary storage, 256 MiB shared memory, no added capabilities, and no new privileges. Containers have no database, provider, Docker socket, host-file mounts or external network route. Logs are disabled. Idle environments expire after ten minutes; verification and cancellation clean up containers, networks and source volumes. Immutable patch/evidence files remain in a separate broker volume.

Trusted Playwright control and pricing expectations run **outside** the candidate container, through a private CDP connection. Browser routing permits exactly the three target URLs; CSP also blocks connections and external resources. The verifier checks rendered monetary text, counts, quantity controls, empty/one-item behavior, increments/decrements, upper/lower limits, invalid input and repeated additions. The same 12 checks detect the original defect before candidate verification. Expected values are independent integer-cent arithmetic, not target `data-cents` attributes or candidate success messages. Candidate HTTP bytes are hashed before and after execution. Results include candidate, file, container/image and verifier identities. Verifier identity covers the trusted check code and executor policy; versioned screenshots/results are retained without rewriting older evidence.

The interactive preview serves the exact retained candidate script on a separate origin, inside an iframe with `sandbox="allow-scripts"` and no same-origin permission. CSP denies network connections, forms, external resources and embedding by unrelated origins. The gateway rewrites only frozen HTML asset URL prefixes for routing; JavaScript bytes remain identical. Reset replaces the candidate session while preserving the original session. It does not apply a patch to the original fixture. Monaco and its worker load from local assets, without a CDN.

This is a local, approved-JavaScript candidate scope. Chromium runs with its internal OS sandbox disabled inside the constrained container; browser/OS/Docker exploits are outside the demonstrated guarantees. The interactive iframe runs in the visitor's browser: opaque-origin/CSP restrictions protect application data, but do not impose Docker CPU/memory limits on that browser tab. Passing finite checks does not establish correctness for every input or immunity to hostile code. There is no authentication, arbitrary repository access, dependency installation, arbitrary shell tool, external publication or production deployment.

### Restart and evidence semantics

After restart, unfinished repairs are reconciled with actual retained candidate/artifact state, cleanup is requested, and the run is classified **interrupted**. Safe automatic resumption is not established; no verification success is inferred from a checkpoint or container existence. Completed evidence reopens without provider work. Patch/candidate identities are immutable per attempt. Changes require another attempt and cannot inherit an earlier result. Historical captures and structured responses remain tied to their recorded source/verifier versions.

Rejected diagnosis/repair model text is bounded and sanitized before schema/citation validation, retained with its rejection reason, and never accepted as a result. Saved investigation reports are immutable inputs; the editable field is explicitly a draft for the next investigation. Evaluation creates output directories before provider calls and atomically saves completed measurements incrementally; offline regression coverage exercises a nonexistent output directory.

SDK references: [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x), [native LangGraph PostgreSQL saver](https://reference.langchain.com/python/langgraph.checkpoint.postgres). Runtime behavior and locked versions are verified in the milestone tests rather than inferred from documentation alone.
