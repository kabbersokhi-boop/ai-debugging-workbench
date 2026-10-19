# Generalized Patch Audit — G1 engineering review

G1 adds an experimental local **Bring Your Own Repository** source to the existing Patch Audit
workspace. Public GitHub source at an immutable commit and a completed patch can enter the same
general intake/approval/execution/history path for Python and Node. Ordinary repository tests
remain separate from independent verification, which is **not configured** for these audits.

Tested implementation: **`771d544490ad8c00e3b74d5c2e579a00cb2dcff6`**.
Review PR: [#12](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/12).
Final review head: **`refs/pull/12/head`**; its resolved SHA is recorded in the PR body and final
handoff, since a commit cannot embed its own identity. The following evidence/report commit
changes no implementation. This report does not authorize merging, deploying or starting G2.

## Investigation, plan and threat model

Remote main was resolved with `git ls-remote` and fetched before creating
`feature/generalized-patch-audit-g01`, based on `fb2ca281c3ce9c6145b02dc051d1fbd7288e0040`.
The README, AGENTS, architecture, Patch Audit reports, evaluator/catalog/broker/runner,
admission/service/routes, frontend and existing tests were inspected before implementation.

The historical catalog pins source manifests and four allowed production scopes. Its patch
admission uses an exact-context parser plus Git application; the broker rebuilds the admitted
record, executes ordinary/independent phases in separate Docker environments, and binds results
to source/candidate/verifier/runtime identities. PostgreSQL stores candidates and executions;
the recorded server imports no execution authority. These mechanisms were preserved.

The historical runner's fixed source/command assumptions cannot safely accept unfamiliar projects.
The implementation adds a separate adapter under `repository_audit`, reuses strict patch admission,
shares the broker's single execution capacity and cleanup lifecycle, and adds versioned source,
candidate, plan and result contracts. No repository is added to the historical task catalog.

Untrusted material includes every source file, patch, README, workflow, package script, setup hook,
dependency and test. Intake/admission must never execute it in the host/API. Trusted components
are GitHub HTTPS metadata for repository-to-commit association, the local owner, application,
PostgreSQL, broker, pinned runtime tools, Docker daemon and host kernel. The broker has host Docker
authority and must remain private. A hostile local administrator or a compromised Docker/kernel is
outside this boundary. Docker alone is not a complete defense against intentionally malicious code;
use a disposable VM for adversarial repositories. G1 is not a public arbitrary-code runner.

## Intake and admission

The API accepts typed `owner/repository` plus a full lowercase 40-character commit, never a supplied
network URL. It uses only HTTPS GitHub API/codeload endpoints without credentials/proxy inheritance;
redirects, alternate hosts/schemes/ports and embedded credentials are rejected. Commit resolution
must return exactly the requested SHA. The bounded archive is read as inert bytes, compared against
the GitHub tree/blob identities, and its complete Git tree is recomputed. There is no checkout,
submodule recursion, Git hook/filter invocation, package install or project import.

Limits: 20,000 KiB GitHub-reported repository size; 1,000 regular files; 1 MB/file; 8 MB source;
8 MB compressed and 16 MB expanded archive; 45-second total fetch budget. Special files, symlinks,
submodules, LFS pointers, export-filter omissions/rewrites and unsupported paths fail explicitly.
Source bytes/modes, file SHA-256s, Git tree, normalized tree identity, fetch/archive metadata and
available license/attribution are preserved.

Patches preserve exact original UTF-8/LF bytes and their hash. The existing dual-parser admission
checks exact hunk positions/context without repair or fuzzy application. G1 allows up to 64 KiB,
four explicitly approved existing production files and 64 hunks/file. Traversal, stale context,
renames/new/deleted files, mode/symlink/binary changes and unsupported no-newline markers are rejected.
Tests/setup/configuration are excluded by a general conservative scope policy. This policy protects
verification inputs from direct patching; it does not make ordinary tests immune to influence from
the production code they import. No filename is presented as a complete security boundary.

## Execution plans and environment

`repository-plan-v1` is an immutable local plan identifying source, candidate software hash,
Python 3.12/Node 22 preset, actual runtime image ID, relative working directory, setup/test argument
vectors, selected-test description, offline dependency policy, wall-clock budget and sandbox policy
hash. A prepared plan is unapproved. Starting a run requires explicit approval of that exact plan
and candidate; the broker repeats admission. Repository instructions are never accepted as approval.

Python reuses the pinned pytest 8.3.5 evaluator image. Node has a digest-pinned 22.22.0 image with
Mocha 11.7.5 and a committed npm integrity lock. Only trusted runtime tools install at image build
time; no target repository is used as a Docker build context. Setup, lifecycle hooks and tests run
only in the disposable container, using argv through Docker exec rather than a host shell.

Actual Docker settings are inspected and checked before project commands: no network or host bind
mounts/socket/credentials/proxy forwarding, UID/GID 1000, read-only root/source, all capabilities
dropped, no new privileges, 1 CPU, 512 MiB memory/swap ceiling, 64 PIDs, 128 MiB scratch, 8 MiB tmp,
8 MiB shm and 16 MiB per-file limit. Output is bounded to 64 KiB per stream per command and marked
when truncated. Docker logs are disabled. The approved 1–120 second command budget includes setup.
Dependencies must be available offline; setup failure prevents test success.

Source/tests remain read-only. Scratch/dependency output goes under `/work`; Python can use
`/work/deps`, Node `/work/node_modules`. Projects needing writable source, online resolution,
unsupported native environments, private credentials or elevated privileges fail instead of
weakening isolation. These are intentional G1 limits, not claims of framework-wide support.

Cleanup follows the same actual Docker resource IDs through uncertain/time-limited removals and
requires confirmed absence before a passing result. Cancellation requests stop the environment;
restart reconciles validated terminal evidence without executing again, or records interruption.
An unavailable Docker daemon can delay/prevent cleanup; this remains an infrastructure failure.
Inherited startup cleanup labels span local verification projects, so active execution stacks must
not be restarted concurrently. The recorded server has neither these routes nor this authority.

## Declared external examples and genuine results

Examples were selected before final evaluation: **hynek/first** (MIT) and
**component/escape-html** (MIT). They were not chosen by searching for passing outcomes.
The [data-only manifest](../../evaluation/repository-examples/g1/examples.json) contains pinned
identities, commands, source references and predeclared expected outcomes. It is not a task adapter.

| Example | Immutable upstream base | Patch source | Selected ordinary result |
| --- | --- | --- | --- |
| Python: `hynek/first` | `106ee3cf389cf2bb76f2816bf22a845c44275f94` | Exact production-only upstream `c91895d9298d32d9302e759b40cff7f0f015bd93`: argument order/default documentation | 3 existing tests passed; two read-only pytest cache warnings |
| Node: `component/escape-html` | `b42947eefa79efff01b3fe988c4c7e7b051ec8d8` | Reinstates historical `String(string)` implementation from parent `a1516acc06e03cea74c4f57f381d7c9e8eb22d05` of performance change `6af479fd7e7173d7c7c87ad8c850dd4fd9bc3667`, adapted to current style | 30 existing tests passed |
| Node negative control, same base | `b42947eefa79efff01b3fe988c4c7e7b051ec8d8` | Explicitly authored `<` → `&gt;` escaping regression; upstream tests unchanged | 24 passed / 6 failed |

Exact patches: [Python](../../evaluation/repository-examples/g1/hynek-first.patch),
[Node historical alternative](../../evaluation/repository-examples/g1/escape-html.patch),
[declared negative control](../../evaluation/repository-examples/g1/escape-html-regression.patch).
The Node alternative is historically sourced, not claimed as a newly discovered bug fix.
The negative control is not an AI-generated patch. The six related failures exercise one authored
regression, not six independent discoveries. Both passing candidates passed only these selected
ordinary tests. No independent detection or model-comparison result is claimed.

Exact commands executed in the respective sandbox working directories:

```sh
python -m pytest -q test_first.py
node /opt/test-tools/node_modules/mocha/bin/mocha.js test/index.js
```

Both repositories use the same source, admission, plan, broker, persistence and UI implementations.
Only runtime/argv and data differ. No source branch dispatches on either repository name.
API and browser executions are repeats of the same candidates, not independent software discoveries.
API counts remain unknown; counts above come from retained framework output.

## Evidence, reproduction and browser walkthrough

A source ID identifies full inert base bytes and fetch metadata. Candidate software identity binds
repository/base/tree/applied-file hashes; a separate immutable import ID binds the exact diff and
user-declared provenance. Plan identity binds approval inputs. Each execution has a fresh audit UUID.
`repository-result-v1` retains those identities, engine/policy, actual image/container/source hashes,
observed Docker restrictions, exact commands, dependency preparation, timestamps/durations, exit
statuses, bounded stdout/stderr, resource failures and confirmed cleanup. Independent status is
`not_configured`. Saved results and downloads revalidate hashes and bindings on reopening.

Source/candidate/plan PostgreSQL rows have immutability triggers. Terminal broker evidence publishes
atomically under an exclusively claimed UUID. A missing report, setup failure, timeout, cancellation,
infrastructure failure or inconsistent evidence cannot become a pass. Invalid responses remain
unvalidated evidence. Authorship is user-declared. G2 can introduce a versioned trusted independent
check plan; none is implemented here.

Start the local stack, then reproduce actual network validation separately from normal offline CI:

```sh
docker compose up --build -d --wait api
uv run --project backend python scripts/validate_repository_g1.py --confirm-local-execution
uv run --project backend python scripts/browser_repository_g1.py --confirm-local-execution
```

Both scripts read the committed manifest and retain evidence under
`artifacts/repository-audit/external`. Without the confirmation flag they prepare review material
without execution. `--base-url http://127.0.0.1:18010` selects the isolated verification stack.
The browser walks actual source fetch, file scope, patch admission/comparison, command review,
explicit confirmation, live result, evidence download and saved-result reopening. No network/mock
transport substitutes for GitHub in these opt-in runs. Normal CI's browser source is explicitly a
synthetic offline transport fixture; all subsequent DB/broker/container activity is real.

Selected downloads: [Python](assets/generalized-patch-audit-g01/python.json),
[Node](assets/generalized-patch-audit-g01/node.json),
[Node failing control](assets/generalized-patch-audit-g01/node-regression.json).
[Execution index](assets/generalized-patch-audit-g01/external-execution-index.json) lists exact
source/candidate/patch/plan/runtime identities and API/browser execution UUIDs.
[Final evidence audit](assets/generalized-patch-audit-g01/completion-evidence-audit.json) revalidates
all six real API/browser downloads, reopens them after recovery, and checks actual Docker resources
are absent. They contain only public upstream source and synthetic local test data.

Actual browser screenshots:

- [Python source/patch/plan review](assets/generalized-patch-audit-g01/python-review.png).
- [Node source/patch/plan review](assets/generalized-patch-audit-g01/node-review.png).
- [Python ordinary result](assets/generalized-patch-audit-g01/python-result.png).
- [Node ordinary result](assets/generalized-patch-audit-g01/node-result.png).
- [Node failing regression](assets/generalized-patch-audit-g01/node-regression-result.png).

Full browser downloads are retained separately as `*-browser.json` in the same evidence folder.
[Browser transcript](assets/generalized-patch-audit-g01/real-browser.log).

## Verification and preservation

All rows below are actual executions of implementation `771d544...`, not reused historical results.
The existing historical test fixtures/results are regression inputs, not new model trials.

| Gate | Actual result and evidence |
| --- | --- |
| `./scripts/check` | **206 passed, 77 deselected**; lint, format, Pyright and frontend build passed. Inherited Monaco bundle-size warning. [Log](assets/generalized-patch-audit-g01/check.log) |
| `./scripts/e2e` | **73 passed, 4 skipped, 206 deselected**, 449.13 seconds. The four existing live-model opt-ins remained disabled. All six new G1 Docker/browser/recovery cases passed. [Log](assets/generalized-patch-audit-g01/e2e.log) |
| Real GitHub API examples | Python 3 passed; Node 30 passed; declared Node regression 24 passed / 6 failed. All downloaded and reopened. [Log](assets/generalized-patch-audit-g01/external.log) |
| Real GitHub browser examples | All three complete journeys passed through live fetch, diff review, approval, execution, download validation and reopen. [Log](assets/generalized-patch-audit-g01/real-browser.log) |
| `./scripts/recovery-smoke` | Completed debugger history unchanged; interrupted work recovered; fresh reproduction succeeded; no cleanup errors. [Log](assets/generalized-patch-audit-g01/recovery.log), [proof](assets/generalized-patch-audit-g01/debugger-recovery.json) |
| G1 cancellation/restart | Cancellation passed; real completed broker result restored without re-execution; missing-terminal run interrupted. [Proof](assets/generalized-patch-audit-g01/repository-recovery.json) |
| `scripts/check_release.py` | Actual non-root/read-only recorded container, no mounts/socket/Docker/workbench authority/credentials, zero execution slots, G1 GET routes 404 and POST routes 405. [Proof](assets/generalized-patch-audit-g01/recorded-boundary.json) |
| Recorded-container browser suite | **2 passed, 281 deselected**; both existing recorded experiences work without mutation requests. [Log](assets/generalized-patch-audit-g01/recorded-browser.log) |
| GitHub implementation CI | **Passed**, credential-free workflow on `771d544490ad8c00e3b74d5c2e579a00cb2dcff6`. [Run 39314835460](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/39314835460), [snapshot](assets/generalized-patch-audit-g01/ci-implementation.json) |
| Final review checks | The report/evidence-only head is covered by [PR #12 checks](https://github.com/kabbersokhi-boop/ai-debugging-workbench/pull/12/checks); exact final head and run are recorded in the PR handoff. |

Normal CI is network-independent with respect to target GitHub repositories: its source/patch
fixtures are synthetic offline data. It still builds the locked application/runtime dependencies.
Real network fetches above were bounded opt-in integration runs and are separate from CI.
The 82 new offline cases cover identifier/URL/redirect/SHA/size/archive/path/patch/plan/no-import
boundaries, missing setup/output, evidence/identity/policy/cleanup failures and local/recorded access.
The actual Docker cases check non-root execution, denied external network/source writes, absent
credentials/socket/bind mounts, resource settings, setup failure, timeout and cancellation.

To reproduce the isolated verification without changing owner volumes:

```sh
export COMPOSE_PROJECT_NAME=patch-audit-g1
export WORKBENCH_DB_PORT=55429 WORKBENCH_API_PORT=18010 WORKBENCH_PREVIEW_PORT=18013
export DATABASE_URL=postgresql+asyncpg://workbench:workbench@127.0.0.1:55429/workbench
export E2E_BASE_URL=http://127.0.0.1:18010 E2E_PREVIEW_URL=http://127.0.0.1:18013
# Exclude owner provider credentials from every verification/recovery invocation.
cat > /tmp/g1-compose.yaml <<'YAML'
services:
  api:
    env_file: !reset []
YAML
export COMPOSE_FILE="$PWD/compose.yaml:/tmp/g1-compose.yaml"
docker compose up --build -d --wait api
./scripts/check
uv run --project backend python -m workbench.evaluator.experiment_cli import
./scripts/e2e
./scripts/recovery-smoke
# Separate restricted recorded image, never deployed publicly:
RECORDED_PORT=18020 docker compose -p patch-audit-g1-release -f compose.release.yaml up --build -d --wait
RELEASE_COMPOSE_PROJECT_NAME=patch-audit-g1-release RELEASE_BASE_URL=http://127.0.0.1:18020 \
  uv run --project backend python scripts/check_release.py
E2E_BASE_URL=http://127.0.0.1:18020 ./scripts/e2e -k recorded_explorer_first
```

The temporary Compose override contains only `services: {api: {env_file: !reset []}}`.
`COMPOSE_FILE` included it during recovery commands as well. No override file contains credentials.
[Preservation and running-source audit](assets/generalized-patch-audit-g01/preservation.json)
checks **1,153** preexisting protected files against the starting main, including all historical
experiments, fixtures, recordings, reports and evaluator/repair/RAG modules. All are byte unchanged.
The actual API and broker source hashes match the tested implementation and contain no supplied
provider credentials. `v1.1.0` remains `49e6071938c8a81aa735cb49b7e18e86679bb7b5`.
The only Patch Audit broker change registers the separate G1 handlers.

Development failures were retained and corrected, not hidden: shell sandbox restrictions blocked
async thread wakeups (offline checks passed outside it); a browser helper initially lacked an import;
a real Docker removal returned an uncertain response and subsequent 409, producing no passing result.
The cleanup regression now polls the same identity and retains structured infrastructure failures.
A confirmation-checkbox layout issue found in the real screenshot was also corrected. No expected
upstream test outcomes were changed to accommodate observed failures.

Historical source/task manifests, verifier/scoring modules, candidates, experiment failures,
recordings, release assets and v1.1.0 tag are preserved. The existing public deployment is not changed.
Verification uses a separate Compose project, ports and PostgreSQL volumes with provider credentials
excluded. There are no model calls, new generation experiments, merges, visibility changes or deployments.

## G2 readiness

G1 supplies reusable source/candidate/plan/execution identities and ordinary checks. G2 still needs
independently specified behavioral requirements, trustworthy external check plans and a method for
validating generated checks; passing an upstream command supplies none of that evidence. Private
credentials, PR integration, broader ecosystems, multi-repository validation and public execution are
outside G1. Stop for engineering review before beginning G2.

**GO for G2 engineering design after G1 review.** G1's bounded local acceptance gate is met.
This is no recommendation for public execution or a claim that independent-check generation works.

| G1 criterion | Authoritative evidence |
| --- | --- |
| A — unfamiliar public repository + immutable base | Both retained source snapshots, Git tree recomputation, live HTTPS fetch/browser transcripts |
| B — matching patch review before execution | Exact retained patch bytes, candidate original/modified text and review screenshots |
| C — trusted explicit ordinary-test plan | Immutable saved plans and candidate/plan-bound approval records; unapproved-plan regressions |
| D — restricted local execution | Observed Docker settings in all real results; real containment/resource/cleanup integration tests |
| E — source/candidate/runtime/plan binding | Result/source/patch hashes and six-report final evidence audit |
| F — download and reopen | All six API/browser reports re-downloaded byte-identically after recovery |
| G/H — genuine external Python and Node | `hynek/first` 3 ordinary tests and `component/escape-html` 30 ordinary tests, real pinned source |
| I — same generalized implementation | Shared module path and runtime-only differences; example names occur only in data/docs/tools |
| J — independent not configured | Every real result and screenshot; no combined verified verdict |
| K — historical behavior intact | 206 offline + 73 integration passes, recorded browser checks and 1,153-file preservation audit |
| L — recorded server has no G1 authority | Restricted image/module/mount audit, all generalized routes absent, zero execution slots |

No G2 implementation, private GitHub access, public execution, model experiment, PR comment automation,
release/tag mutation, merge or deployment was performed. The PR remains for engineering review.
