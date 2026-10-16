# Approved external tasks · evaluator milestone 1

These two public historical defects are reproducible tasks, not a statistically representative
benchmark or an uncontaminated measure of agent ability. Upstream solutions are public.

| Task | Pinned defective base | Upstream evidence | License |
| --- | --- | --- | --- |
| more-itertools false-valued bucket validator | `1ea82a711c69f590054987b5cb194157f8ce8ac4` | [Issue 1308](https://github.com/more-itertools/more-itertools/issues/1308), [correction](https://github.com/more-itertools/more-itertools/commit/67fcf640477c78605580f5ee703a54c73c1e7a8a) | MIT |
| Boltons one-shot addlist inputs | `d45cc414e33aa4e08a73e0993574df4397e2e9db` | [PR 458](https://github.com/mahmoud/boltons/pull/458), [correction](https://github.com/mahmoud/boltons/commit/a1ea1030ed85137e999c0bd9b11d16368d3ab241) | BSD 3 clause |

`tasks/*/source/` contains narrow, byte-for-byte source and applicable upstream test snapshots,
including upstream licenses. These are approximately 600 KB total, not complete repositories.
Each manifest lists SHA-256 identities. Nothing in the upstream source or tests is changed to
accommodate candidates. More-itertools ordinary scope is its existing `BucketTests` class;
Boltons ordinary scope is its existing dictutils and urlutils test modules. This is not a claim
that the entire upstream suite ran.

## Run locally

Use the repository's normal Python 3.12 / uv / Node prerequisites and a local Docker daemon.

```sh
uv sync --project backend --frozen
npm ci --prefix frontend
docker compose up --build -d --wait api
```

Open `http://127.0.0.1:8010/?workspace=evaluation`, or choose **Agent Evaluation** in the debugger.
Select a task and candidate, inspect the diff, run checks, open a mismatch, and download evidence.
History and copied evaluation links reopen PostgreSQL records without inference. Cancellation
requests kill the executing container and retain terminal evidence. Restart recovery reconciles
available terminal broker evidence; otherwise it marks interrupted work without inferring a pass.

For a deterministic authored failure, from the repository root:

```sh
docker build -f docker/evaluator.Dockerfile -t ai-agent-evaluator:python312-v1 .
uv run --project backend python -m workbench.evaluator.cli more-bucket-negative
uv run --project backend python -m workbench.evaluator.cli boltons-addlist-negative
```

Each command exits 1 because independent checks fail; the JSON includes actual commands, logs,
expected and observed values, source hashes and container identity. Substitute `-reference` or
`-alternate` to reproduce valid corrections (exit 0), or `-baseline` for the original defects.
Results apply only to their recorded image, policy, source, patch, specification and verifier.
Rebuilding an image can produce a different image identity; compare identities before claiming
an exact reproduction. There is no provider request in evaluation or reproduction.

## Artifact policy and generation separation

Specifications, checks, source, reference controls and negative controls are public-review artifacts.
They are **not confidential**. No hidden-test or training-contamination claim is made.

Before generation, controls validate the task and `freeze-v1.json` binds specification and verifier
hashes, runtime identity and control results. The freeze is committed before provider requests.
`generations/` retains exact approved prompt context, request settings, sanitized responses,
provider model metadata, token usage and all attempted calls. Model output is applied by exact
unique text replacement with an allowlist; it is never manually corrected. The resulting unified
diff is derived from those exact replacements and bound to its complete source identity.

The generator sends an HTTP request with a problem statement and source excerpts only. The
provider has no tools, filesystem mounts, retrieval or access to this coordinator's context.
No expected result matrices, probe scripts, reference corrections or evaluation feedback enter
that request. This verifies request-level separation; it cannot verify what public material a
model encountered during training. This is a single-turn coding-agent configuration, not a
full interactive coding-agent product comparison. Live generation is opt-in:

```sh
uv run --project backend python scripts/generate_evaluator_candidates.py --live
```

Existing attempt IDs cannot be overwritten. Every attempted response, failure or invalid patch is
retained. Further experiments require explicit versioned attempt IDs rather than silently retrying
until a passing patch appears. Offline tests and product evaluation need no provider key.

## Trust boundary

The API persists evidence and calls a private evaluator broker. Only the broker has Docker
authority. It accepts catalog candidate IDs and expected candidate hashes, never user commands,
repository URLs, uploads or target paths. Candidate source never executes in either process.

The broker initializes a named volume with bounded admitted files, reads its contents back through
Docker and hashes the actual bytes. Each phase uses a fresh disposable container with that source
mounted read-only. Ordinary upstream tests are immutable. The independent phase excludes upstream
test files and carries only a fixed behavioral observation probe; expected values and comparison
logic remain outside the candidate container. Exit codes and observations determine outcomes,
not a candidate's printed claim of success.

Containers have no network, host paths, Docker socket or credentials; run as uid 1000 with no
capabilities, default Docker seccomp, no-new-privileges, read-only rootfs, one CPU, 256 MiB memory
and swap cap, 32 PIDs, 32 MiB temporary space, bounded file sizes and rotated logs. Each phase has
a 25 second wall deadline including initialization; cleanup removes its containers and volume.
The broker reaps only its labeled leftovers on restart. Timing and sampled CPU/memory observations
are retained; short executions may finish before sampling. Infrastructure, missing evidence,
timeout, cancellation, invalid output, interrupted work and actual check failure remain distinct.

This is a local allowlisted runner, not a hardened service for adversarial arbitrary code. The
broker's Docker socket grants host-level authority and must never be exposed publicly. Docker
shares the host kernel. A malicious Python module can introspect its own runtime and potentially
game an in-container observation or ordinary test process; the milestone does not establish a
complete anti-gaming boundary against deliberately hostile implementations. Scoring code and
expected matrices are outside its modification authority. Finite checks cannot prove correctness
for all inputs. The inherited debugger browser sandbox limitations still apply to debugger runs;
these two tasks execute no browser or generated scripts in the reviewer's browser.

No evaluator route is added to the recorded release server. Guest live mode rejects this feature.
Do not deploy this execution stack publicly.
