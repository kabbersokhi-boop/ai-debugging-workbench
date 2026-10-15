# AI debugging workbench

**Reproduce a software bug in a real browser. Inspect the evidence behind the outcome.**

Select a retail checkout defect, watch Chromium follow the report, compare baseline and defect screenshots, inspect pricing assertions, and download the Playwright trace. Every run is persisted in PostgreSQL.

Milestone 1 delivers the working reproduction foundation. NVIDIA investigation, repository retrieval, autonomous patches, and independent repair verification arrive in the [next three milestones](docs/ROADMAP.md). They are not simulated here. This repository is private and milestone PRs require owner review.

![Real browser reproduction in the workbench](docs/reports/assets/workspace-reproduced.png)

## Run locally

Requires Docker with Compose. From this milestone branch:

```bash
docker compose up --build -d --wait api
```

Open **http://localhost:8010** and click **Reproduce bug**. No API key is required for milestone 1. The first build downloads the pinned Playwright image and dependencies. The API binds to loopback; this is a local development application, not a public deployment.

The report: one $64 daypack totals $72 with shipping. Set quantity to three: the line amount becomes $192, but checkout incorrectly remains at $64 subtotal plus $8 shipping. The trusted contract expects $192 with free shipping. A completed run shows one passing line-amount assertion and three pricing mismatches.

Choose **Interactive storefront** to try the actual app yourself. That session is separate from automation. Switch **Baseline / Defect** to compare captured states, expand the evidence viewer, or open **Run details** to download screenshots, console output, result JSON, and a native Playwright trace. Select any recent run to reopen persisted evidence.

```bash
docker compose logs -f api runner
docker compose down
```

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

For hot reload, keep the database running and stop the container API/runner:

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

Use Vite's printed URL for UI edits. It proxies `/api` to the API; the fixture is served through `/retail` (also proxied). Use exactly one API worker. Copy `.env.example` to `backend/.env` only if overriding local defaults. Never add inference or infrastructure secrets to the runner or frontend.

Open a trace locally from `backend/` after downloading it:

```bash
uv run playwright show-trace /absolute/path/to/trace.zip
```

## Engineering boundaries

- Actual Chromium execution, actual screenshots and DOM observations; no prerecorded fallback in this milestone.
- A passing one-item control precedes the defect test. Reported defect signatures, all-passing runs, infrastructure errors, cancellation and interruption are distinct outcomes.
- The runner accepts a fixed recipe only, with no arbitrary URL or command. It has no database credentials, no network egress in Compose, a read-only root filesystem, and resource limits.
- PostgreSQL stores ordered events and outcomes transactionally. Idempotency prevents duplicate runs; cancellation cannot be overwritten by a late success. Incomplete runs are marked interrupted after an unclean restart.
- No authentication, arbitrary report ingestion, untrusted code execution, AI inference, retrieval, patches, or repair verification yet. Artifacts have no automatic retention policy. Public hosting requires further work and owner approval.

See [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), [roadmap](docs/ROADMAP.md), and the [milestone engineering report](docs/reports/MILESTONE-01.md). CI runs the same checks and the complete Compose/browser journey, retaining acceptance evidence as a workflow artifact.
