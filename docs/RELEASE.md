# Release candidate boundary

## Two explicit modes

| Mode | Entry point | Execution authority |
| --- | --- | --- |
| Private live workbench | `compose.yaml`, loopback `8010` | Actual NVIDIA / LangGraph / MCP; private broker owns Docker |
| Recorded release | `compose.release.yaml`, loopback `8020` | Read-only saved records; zero provider requests/tokens/execution slots |

The release image contains only a small FastAPI server, built frontend and allowlisted sanitized recordings. It has no database/secret configuration, workbench broker/agent implementation, Docker socket, candidate files mounted as executable content, or live run routes. All mutation methods return 405. Private run/history/artifact APIs are absent. Recordings are shared public evidence; visitors have no private execution records to cross-access.

Per-visitor admission is 120 requests/minute with opaque HttpOnly SameSite=Strict cookies expiring after 15 minutes. At most 1,024 resident sessions and 600 requests/minute globally are admitted. Uvicorn has 32 concurrency slots and a five-second idle connection timeout. Container policy is nonroot, read-only root, no capabilities/new privileges, 192 MiB memory, 0.5 CPU, 32 PIDs and 8 MiB tmp. Immutable recording assets are retained with their release version; there are no uploaded/generated release artifacts or preview environments to expire. Session windows are reaped on requests and reset on restart; this cannot replenish a provider budget because the public process has none.

CSP permits only local application scripts/assets, locally loaded Monaco workers and pixel images; no remote candidate scripts, frames, forms or arbitrary connections. Model/source text is rendered as text or a read-only editor. `nosniff`, no-referrer and frame denial apply. The public surface supports no cross-origin action. Health checks validate the frontend and recording bundle; missing evidence is unavailable, with no live fallback. Access logging is disabled and no secret is supplied to the image.

## Private execution and guests

`compose.guest.yaml` optionally adds session access controls for **private staging**, behind an owner-controlled tunnel. It is not authorization to internet-expose Docker-backed execution. Runs and derived investigations/repairs/artifacts are authorized through a persisted run owner. Historical ownerless rows remain visible only in trusted local mode. Session expiry revokes guest access; idempotency keys are scoped per guest. Cross-origin POSTs are denied. Set `ALLOWED_ORIGIN` to the actual private origin, and use secure cookies when TLS is active.

PostgreSQL row locks persist nonrefundable conservative input/output reservations and request counts across API restarts: default 2,000 requests / 1,000,000 reserved tokens per 24-hour guest session; 20,000 requests / 5,000,000 reserved tokens per UTC day globally. Existing coordinator concurrency limits, deadlines and provider retries remain. Rejected admissions never start provider work. Cookie renewal cannot bypass the global ceiling. These are admission reservations, not measured billing.

The fixed runner receives no NVIDIA credentials and runs only approved frozen scenarios. Candidate networks/volumes are separate from it. Trusted checks hash actual candidate bytes before/after execution and bind source, scenario expectations, verifier and actual candidate image. Cache keys include all those identities; historical passes remain historical. Containers are cleaned after verification/cancellation, idle previews expire after ten minutes, and broker restart reconciles/removes remaining environments. Saved local evidence stays in its named volumes, intentionally retained for owner review and backup; no automatic deletion of historical artifacts is performed.

Candidate interaction is remote: the broker permits only reset/add/increase/decrease, captures bounded PNGs and small text fields, and sends no candidate JavaScript to a visitor tab. A nonresponsive script is stopped and its environment removed; controls cannot submit scripts or shell commands. The obsolete script-delivery gateway returns 410. Container/browser/OS/Docker exploits remain outside this demonstrated private boundary. Playwright itself warns against treating its Docker image as a complete untrusted-web sandbox: [official Docker guidance](https://playwright.dev/python/docs/docker).

## Activation remains blocked on owner authorization

The tested deployment is **localhost only**. No authorized private hosted staging destination was provided, no public URL exists, and no service was purchased or repository visibility changed.

To activate the recorded release, the owner must authorize a hosting account/destination and public TLS origin. Deploy **only** `docker/release.Dockerfile` / the recorded explorer service behind that platform's TLS ingress; set `RELEASE_SECURE_COOKIES=true`, retain one worker and the tested resource/concurrency limits, and verify `/api/health` plus recorded desktop/mobile acceptance at that origin. Do not route the private API, broker control, Docker socket or candidate CDP ports into that deployment. Public live repair would require a separate isolation review and explicit authorization; this release does not claim it.
