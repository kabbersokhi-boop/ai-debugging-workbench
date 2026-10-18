# Release boundary

## Two explicit modes

| Mode | Entry point | Execution authority |
| --- | --- | --- |
| Private live workbench | `compose.yaml`, loopback `8010` | Actual NVIDIA / LangGraph / MCP; private broker owns Docker |
| Recorded release | `compose.release.yaml`, loopback `8020` | Recorded Patch Audit plus original debugger; zero provider requests/tokens/execution slots |

The release image contains only a small FastAPI server, built frontend and allowlisted sanitized recordings. It has no database/secret configuration, workbench broker/agent implementation, Docker socket, candidate files mounted as executable content, or live run routes. All mutation methods return 405. Private run/history/artifact APIs are absent. Recordings are shared public evidence; visitors have no private execution records to cross-access.

In the single-container Compose deployment, per-visitor admission is 120 requests/minute with opaque HttpOnly SameSite=Strict cookies expiring after 15 minutes. At most 1,024 resident sessions and 600 requests/minute globally are admitted. Uvicorn has 32 concurrency slots and a five-second idle connection timeout. Container policy is nonroot, read-only root, no capabilities/new privileges, 192 MiB memory, 0.5 CPU, 32 PIDs and 8 MiB tmp. Immutable recording assets are retained with their release version; there are no uploaded/generated release artifacts or preview environments to expire. Session windows are reaped on requests and reset on restart; this cannot replenish a provider budget because the public process has none.

CSP permits only local application scripts/assets, locally loaded Monaco workers and pixel images; no remote candidate scripts, frames, forms or arbitrary connections. Model/source text is rendered as text or a read-only editor. `nosniff`, no-referrer and frame denial apply. The public surface supports no cross-origin action. Health checks validate the frontend and recording bundle; missing evidence is unavailable, with no live fallback. Access logging is disabled and no secret is supplied to the image.

## Private execution and guests

`compose.guest.yaml` optionally adds session access controls for **private staging**, behind an owner-controlled tunnel. It is not authorization to internet-expose Docker-backed execution. Runs and derived investigations/repairs/artifacts are authorized through a persisted run owner. Historical ownerless rows remain visible only in trusted local mode. Session expiry revokes guest access; idempotency keys are scoped per guest. Guest resource URLs require canonical lowercase, hyphenated UUIDs; alternate spellings and malformed IDs return 404 before resource handlers. Trusted local UUID parsing is unchanged. Cross-origin POSTs are denied. Set `ALLOWED_ORIGIN` to the actual private origin, and use secure cookies when TLS is active.

PostgreSQL row locks persist nonrefundable conservative input/output reservations and request counts across API restarts: default 2,000 requests / 1,000,000 reserved tokens per 24-hour guest session; 20,000 requests / 5,000,000 reserved tokens per UTC day globally. Existing coordinator concurrency limits, deadlines and provider retries remain. Rejected admissions never start provider work. Cookie renewal cannot bypass the global ceiling. These are admission reservations, not measured billing.

The fixed runner receives no NVIDIA credentials and runs only approved frozen scenarios. Candidate networks/volumes are separate from it. Trusted checks hash actual candidate bytes before/after execution and bind source, scenario expectations, verifier and actual candidate image. Cache keys include all those identities; historical passes remain historical. Containers are cleaned after verification/cancellation, idle previews expire after ten minutes, and broker restart reconciles/removes remaining environments. Saved local evidence stays in its named volumes, intentionally retained for owner review and backup; no automatic deletion of historical artifacts is performed.

Candidate interaction is remote: the broker permits only reset/add/increase/decrease, captures bounded PNGs and small text fields, and sends no candidate JavaScript to a visitor tab. A nonresponsive script is stopped and its environment removed; controls cannot submit scripts or shell commands. The obsolete script-delivery gateway returns 410. Container/browser/OS/Docker exploits remain outside this demonstrated private boundary. Playwright itself warns against treating its Docker image as a complete untrusted-web sandbox: [official Docker guidance](https://playwright.dev/python/docs/docker).

## Recorded-only Vercel deployment

The owner authorized the existing Vercel account for this release. Its team uses the Hobby plan.
No upgrade, purchase, custom DNS or privileged live service is authorized. The final externally
verified URL belongs in the README and release notes.

Vercel's native FastAPI runtime exports the existing recorded server through the small
`app.py`; root `requirements.txt` mirrors the pinned `docker/release-requirements.txt`
(byte equality is checked in CI; Vercel rejected a requirements include directive).
`vercel.json` runs the existing frontend build and includes only its output and curated recordings.
No new framework/service is added. This avoids the Container Runtime registry storage charge.
Set only the nonsecret `RELEASE_SECURE_COOKIES=true`; supply no provider/database credentials.
Never deploy the privileged root `Dockerfile` or attach its normal Compose services.

After committing and verifying the release head, prepare an allowlisted bundle from that commit:

```sh
release_bundle=$(mktemp -d)
git archive HEAD app.py requirements.txt vercel.json .vercelignore .python-version docker/release-requirements.txt \
  backend/src/workbench/release.py frontend recordings .dockerignore |
  tar -x -C "$release_bundle"
vercel link --project ai-debugging-workbench-recorded --scope mogging20202020 --cwd "$release_bundle"
vercel deploy --prod --cwd "$release_bundle"
```

Only this bundle is deployed: no evaluator, local secrets, backups or private execution modules.
Vercel runs FastAPI as autoscaled Functions. Compose CPU/memory/PID/capability, network and tmpfs
settings are **local container checks, not verified Vercel settings**. Request/session windows are
per process and reset with recycling, not a deployment-wide quota. The top-level recorded
middleware remains active, including for static files; do not force static CDN promotion.
Keep existing Hobby limits; exceeding a free limit can pause service. Do not enable paid capacity.
[FastAPI runtime](https://vercel.com/docs/frameworks/backend/fastapi) ·
[Hobby included usage](https://vercel.com/docs/plans/hobby).

Verify unauthenticated HTTPS, both audits, exact diffs/evidence downloads, the original recorded
debugger, health/security headers, and absent mutation/private routes. No public patch import,
candidate execution, model call, database or broker is permitted.

## Isolated release verification

Normal ports and project names remain defaults. To leave existing owner volumes/services intact:

```sh
export COMPOSE_PROJECT_NAME=patch-audit-verify
export WORKBENCH_DB_PORT=55429 WORKBENCH_API_PORT=18010 WORKBENCH_PREVIEW_PORT=18013
export DATABASE_URL=postgresql+asyncpg://workbench:workbench@127.0.0.1:55429/workbench
export E2E_BASE_URL=http://127.0.0.1:18010 E2E_PREVIEW_URL=http://127.0.0.1:18013
docker compose up --build -d --wait api
./scripts/check
./scripts/e2e
./scripts/recovery-smoke
export RELEASE_COMPOSE_PROJECT_NAME=patch-audit-release-verify
export RECORDED_PORT=18020 RELEASE_BASE_URL=http://127.0.0.1:18020
docker compose -p "$RELEASE_COMPOSE_PROJECT_NAME" -f compose.release.yaml up --build -d --wait
uv run --project backend python scripts/check_release.py
E2E_BASE_URL=$RELEASE_BASE_URL ./scripts/e2e -k recorded_explorer_first
```

This uses separate named volumes. The owner stack must be idle: broker cleanup labels identify
disposable candidate environments across projects. Recovery subprocesses inherit
`COMPOSE_PROJECT_NAME`; never omit it for isolated testing. Do not remove owner volumes or reset
its database. Four live-provider opt-in tests remain skipped unless separately requested.
