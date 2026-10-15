# AI debugging workbench

**Reproduce a bug. Investigate its source. Inspect and independently check a model-generated candidate.**

Select a retail checkout defect, watch Chromium follow the report, compare baseline and defect screenshots, inspect pricing assertions, and download the Playwright trace. Every run is persisted in PostgreSQL.

The workbench combines real NVIDIA diagnosis, frozen repository retrieval, a typed LangGraph repair workflow, real MCP source tools, disposable candidates, and trusted browser verification. Inspect the diff and interact with original/candidate storefronts. No model response is simulated in the application. This repository is private and milestone PRs require owner review.

![Real browser reproduction in the workbench](docs/reports/assets/workspace-reproduced.png)

## Run locally

Requires Docker with Compose. From this milestone branch:

```bash
docker compose up --build -d --wait api
```

Open **http://localhost:8010** and click **Reproduce bug**. Browser reproduction needs no key. For diagnosis, set `NVIDIA_API_KEY=...` in ignored `backend/.env` before starting Compose; the file should have mode 0600. Only the API receives it. Never paste a credential into the UI. The first build downloads the pinned Playwright image and dependencies. The API binds to loopback; this is a local development application, not a public deployment.

The report: one $64 daypack totals $72 with shipping. Set quantity to three: the line amount becomes $192, but checkout incorrectly remains at $64 subtotal plus $8 shipping. The trusted contract expects $192 with free shipping. A completed run shows one passing line-amount assertion and three pricing mismatches.

Choose **Interactive storefront** to try the actual app yourself. That session is separate from automation. Switch **Baseline / Defect** to compare captured states, expand the evidence viewer, or open **Run details** to download screenshots, console output, result JSON, and a native Playwright trace. Select any recent run to reopen persisted evidence.

```bash
docker compose logs -f api runner
docker compose down
```

After reproduction, select **Investigation** and **Investigate with NVIDIA**. Inspect the proposed diagnosis, click a citation, compare candidates with supplied snippets, and reopen saved investigations. Older Milestone 1 runs need a new reproduction to match the frozen source snapshot.

`down` preserves named volumes. Run history and artifacts remain available on the next start. To force a new image after source changes, repeat the first command.

## Develop and check

Requires Python 3.12, uv, Node 22.12+ and Docker. Dependency lockfiles are committed.

```bash
uv sync --project backend --frozen
npm ci --prefix frontend
uv run --project backend playwright install chromium
./scripts/check

# Run the real PostgreSQL/API/browser acceptance suite against Compose:
docker compose up --build -d --wait api
./scripts/e2e
# Optional crash/recovery check against this local Compose stack, after e2e:
./scripts/recovery-smoke
```

`check` runs Ruff, format checks, Pyright, unit tests, TypeScript and the production UI build. `e2e` runs browser/API tests and lifecycle integration tests using PostgreSQL in disposable schemas. It requires the API at `http://127.0.0.1:8010` and PostgreSQL at `127.0.0.1:54329`. Use `E2E_BASE_URL` and `DATABASE_URL` to override those endpoints. Linux hosts may need Playwright's documented system dependencies (`playwright install --with-deps chromium`); the application containers already include them. Acceptance captures are written to ignored `artifacts/acceptance/`.

For reproduction/diagnosis hot reload, keep the database running and stop the container API/runner. Use the full Compose app on port 8010 for the repair flow; its private executor and preview origin are configured for that stack:

```bash
docker compose stop api runner
cd backend
uv run alembic upgrade head
uv run uvicorn workbench.runner:app --host 127.0.0.1 --port 8011
# In another terminal, from backend/:
uv run uvicorn workbench.api:app --host 127.0.0.1 --port 8010 --reload
# In another terminal, from frontend/:
npm run dev
```

Use Vite's printed URL for UI edits. It proxies `/api` to the API; the fixture is served through `/retail` (also proxied). Use exactly one API worker. Runtime connection overrides use environment variables; `backend/.env` is read only by provider configuration locally and by Compose for the API. Asset defaults are anchored to the repository rather than the current directory. Never add inference or infrastructure secrets to the runner or frontend.

Open a trace locally from `backend/` after downloading it:

```bash
uv run playwright show-trace /absolute/path/to/trace.zip
```

## Engineering boundaries

- Actual Chromium execution, actual screenshots and DOM observations; no prerecorded fallback in this milestone.
- A passing one-item control precedes the defect test. Reported defect signatures, all-passing runs, infrastructure errors, cancellation and interruption are distinct outcomes.
- The runner accepts a fixed recipe only, with no arbitrary URL or command. It has no database credentials, no network egress in Compose, a read-only root filesystem, and resource limits.
- PostgreSQL stores ordered events and outcomes transactionally. Idempotency prevents duplicate runs; cancellation cannot be overwritten by a late success. Incomplete runs are marked interrupted after an unclean restart.
- Repairs are limited to the approved cart.js snapshot and named trusted checks. Generated JavaScript runs in separate constrained containers and an opaque preview iframe. There is no authentication, arbitrary repository ingestion, shell tool or publication agent. Artifact retention is manual. Public hosting requires further work and owner approval.

See [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), [roadmap](docs/ROADMAP.md), and the [Milestone 1 report](docs/reports/MILESTONE-01.md) [Milestone 2 report](docs/reports/MILESTONE-02.md), and [Milestone 3 report](docs/reports/MILESTONE-03.md). CI runs the same checks and the complete Compose/browser journey, retaining acceptance evidence as a workflow artifact.


## Live providers and evaluation

Successfully tested defaults: `nvidia/nemotron-3.5-super-vl-120b-a12b` for chat, `nvidia/nemotron-3-embed-1b` for 2,048-dimensional embeddings, and `nvidia/llama-nemotron-rerank-vl-1b-v2` for native text-passage reranking. Several older catalog routes returned 404/410; the report retains those failures. Models are replaceable through a provider protocol. LangChain handles diagnosis prompt composition and structured parsing. The bounded repair workflow uses LangGraph and actual MCP tools.

```bash
# Explicit live acceptance; calls NVIDIA, unlike deterministic offline tests:
LIVE_NVIDIA_E2E=1 ./scripts/e2e -k live_nvidia_investigation

# Frozen eight-query retrieval suite and same-model retrieved/whole-target comparison:
uv run --project backend python scripts/evaluate.py --live --run-id <matching-reproduction-uuid>
```

Runtime results go to ignored `artifacts/milestone-02/`. The evaluated corpus is frozen at commit `b44dfbb5c6804638e42d2dcc76565aa8d12aeb2a`; source bytes are also persisted in PostgreSQL. `evals/` and trusted reproduction checks are excluded from ingestion. Live tests require explicit opt-in and credentials; CI uses deterministic provider fixtures for contracts/failures plus actual PostgreSQL and browser reproduction.

The measured smoke suite does **not** establish a RAG accuracy gain: lexical recall@5 was 100%, versus 83.3% for hybrid with reranking. Whole-target context also diagnosed this one defect. The report records a rejected invalid citation on the no-answer retrieved-context case. These are small-sample engineering observations, not general debugging benchmarks or verified repairs. Provider dollar pricing was unavailable.


## Milestone 3: inspect and verify a candidate

After reproducing the approved defect and completing a diagnosis, open **Investigation → Generate candidate with NVIDIA**. The graph can read missing frozen source through MCP, propose up to two cart.js patches, execute a disposable candidate, and request the independent pricing browser checks. Inspect the local Monaco diff, exact candidate hash, named checks, tool evidence and attempt history. Use **Start / reset candidate preview** to compare the original and candidate in separate browser sessions. Patch and complete-evidence downloads do not publish application changes.

Compose now also builds the minimal candidate image and starts a trusted Docker broker. Docker must be available at `/var/run/docker.sock`; only the broker mounts that socket. The preview binds to `127.0.0.1:8013`; the workbench remains at `http://127.0.0.1:8010`. The fixed reproduction runner receives no provider/database secrets and remains a fixed trusted procedure. Existing PostgreSQL and evidence volumes are preserved by additive migrations. **Do not use `docker compose down -v` to upgrade.**

```bash
./scripts/check
./scripts/e2e                         # offline providers + real MCP/Docker/browser checks
LIVE_NVIDIA_REPAIR=1 ./scripts/e2e -k live_nvidia_repair  # explicit real-provider opt-in
./scripts/recovery-smoke
```

Deterministic model responses/negative patches occur only in clearly labeled offline tests. The runtime never substitutes them for NVIDIA. Verification means the named checks passed for that exact candidate and verifier version; it is not a guarantee for all inputs. [Isolation and checkpoint boundaries](docs/ARCHITECTURE.md#bounded-repair-milestone-3) describe actual guarantees and limitations. Milestone PRs remain unmerged and private; no candidate is autonomously published.
