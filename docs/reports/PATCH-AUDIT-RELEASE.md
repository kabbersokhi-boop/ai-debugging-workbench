# Patch Audit release · 2026-10-18

This is a release of the accepted bounded Patch Audit workflow, not another experiment.
The broader agent-comparison milestone remains on hold. Exact final commit, CI, tag and hosted
URL are recorded in the GitHub release notes to avoid a commit embedding its own identity.

## Integration and product

Accepted PRs #6, #7 and #8 were retargeted as needed and merged into `main` with ordinary merge
commits. Accepted final review head `1959cd98e0681e3039838721a30fae5cf2d895f9` and guest-authorization
correction `e860ed6` are ancestors. Original branches and review tags remain; no squash, rebase,
force push or history deletion was used. The release preparation changes presentation, isolated
verification configuration and the recorded hosting entrypoint; it does not change evaluator scoring.

The root opens Patch Audit. Four pinned Python tasks support exact-base patch review and explicit
local execution. Import alone does not execute. Fresh ordinary and independent checks, persistent
audits, exact patches, downloads and reopening remain available. The debugger and Agent Evaluation
workspaces are preserved. Recorded release has two curated audit examples and the old debugger.

The incomplete development repair passed 155 selected tests but missed the standalone Boltons copy.
Its related failed observations describe one incomplete repair. The passing example came from a
different generation procedure. These are not a fair vendor comparison. M1 had no genuine additional
discovery; formal m02-v1 remains **0/6** among ordinary-passing submissions, with 24 attempts total.
Separate development evidence remains **1/1**, with three other journeys producing no submission.
Readiness failed; no subsequent formal experiment or new model call was run for this release.

## Publication check

Local Gitleaks 8.30.1 was downloaded from its official release and checksum verified. All 50 reachable
history commits across branches/tags and 1,274 tracked/proposed files were scanned before release
preparation was committed. Nine findings in three evidence JSON files were inspected: all are public
SHA-256 source/preservation identities, not credentials. Local targeted history/content searches
found no likely real retained token, private key, credential-bearing env file, signed private link,
database dump or customer input. Ignored local credentials and backups remain excluded.

All 49 retained Actions artifacts and 49 workflow log archives, plus 32 PR/issue/review documents
for PRs #1–#8, were downloaded locally and scanned; none produced a scanner finding. Existing
accurate synthetic screenshots were sampled visually. No private source went to a scanning service.
This is a bounded publication check, not a complete security audit: unknown formats, encoding,
binary payloads and unreviewed video frames remain limitations. Later release commits and relevant
CI artifacts are checked again before publication.

CI uses a hosted ephemeral runner, `contents: read`, checkout without persisted credentials and
no provider secrets. There is no `pull_request_target` or persistent privileged contributor runner.
No project license is granted; existing upstream licenses and attribution remain intact.

## Verification and deployment boundary

Exact commands and environment overrides are in [release instructions](../RELEASE.md#isolated-release-verification).
The live test project uses separate PostgreSQL/evidence volumes and ports; the owner's existing
stack remains intact. Historical freezes and all 1,097 protected files validate unchanged.

The Vercel entrypoint reuses the existing recorded FastAPI server and exact pinned requirements;
its build command reuses the frontend build. Only an allowlisted committed bundle is deployed
to the owner-approved existing Vercel Hobby account.
It contains the recorded server, frontend and curated records, with no provider/database secrets,
Docker socket, broker or live import/execution endpoints. Only nonsecret secure-cookie configuration
is supplied. The native runtime avoids container-registry storage pricing. No paid upgrade or custom DNS is
authorized. Vercel autoscaling means process-local
request windows are not global quotas; local Compose resource limits are not claims about Vercel.

Containers and in-process Python observations are not a complete anti-tampering boundary against
malicious code. Passing finite named procedures does not establish universal correctness or security.

The first local Vercel build rejected a requirements include directive; its failure log is retained.
Root requirements now mirror the exact recorded pins, with byte equality enforced in CI.

Retained initial verification failures: integrated-main CI run 39144571702 measured mobile width
immediately after a Monaco resize; the local recovery script's Compose startup let the run finish
before its kill request. The diff host now contains transient editor width, the test awaits the
same viewport-fit condition, and recovery resolves the Compose API first then kills it directly.
Neither assertion nor application result scoring was relaxed. The initial native build also mapped
a CLI-generated local environment file; explicit source and function exclusions remove env files.

Local verification: `scripts/check` passed 124 offline tests, typing/lint and the frontend build.
The isolated full `scripts/e2e` passed 67 integration/browser tests with four explicit live-provider
skips. Fresh retained incomplete/complete imports, confirmation, execution, download and reopening
passed; these are re-audits, not new generation trials. Recorded image boundary and both recorded
browser journeys passed. The corrected recovery smoke interrupted a running reproduction, preserved
completed history and reproduced a fresh run afterward. Fingerprints of all rows across 14 owner
database tables remained unchanged. The native Vercel build completed, with environment/private
backend files absent from its function map after exclusions. Final CI/external verification links
and the exact tested main commit are in the release notes.
