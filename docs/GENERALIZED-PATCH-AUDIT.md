# Local external repository audits (G1)

Start the private stack with `docker compose up --build -d --wait api`, open
<http://127.0.0.1:8010/>, and select **External repository (experimental)**.
The public recorded application cannot import or execute repositories.

1. Enter a public GitHub `owner/repository` and a full 40-character base commit.
2. Fetch and review the identity and license. No project code runs during intake.
3. Select up to four permitted production files and paste or upload a matching unified diff.
4. Review the exact patch and source comparison.
5. Select Python 3.12 or Node 22 and enter explicit test arguments as a JSON array.
   Setup is a JSON array of argument arrays. No host shell interpolates these values.
6. Prepare the plan, review its exact runtime image, commands and source binding,
   then explicitly approve local execution.
7. Inspect ordinary output, download the source-bound evidence, and reopen history.

Python includes pytest 8.3.5. Node includes the built-in test runner and locked Mocha 11.7.5:

```json
["python", "-m", "pytest", "-q", "tests"]
["node", "--test"]
["node", "/opt/test-tools/node_modules/mocha/bin/mocha.js", "test/index.js"]
```

These are suggestions, not an assertion that a particular project supports them.
A plan runs only after explicit owner approval. Dependency setup, package scripts,
plugins and lifecycle hooks are all untrusted execution.

## Supported preparation and restrictions

Source and tests stay read-only at `/source`. Relative plan working directories resolve
under that root. Use `/work` for disposable scratch space and `/work/deps` for offline
Python dependencies; `/work/node_modules` is on `NODE_PATH`. `/tmp` is also disposable.
For example, an owner can approve `pip install --no-index --no-deps --target /work/deps
/source/vendor/package.whl` when a reviewed, pinned wheel is already present in source.
G1 fetches no dependency URLs and grants no network route to package managers.

Projects needing writable source trees, online dependency resolution, unsupported native
system packages, private credentials, submodules, symlinks or LFS need a different
preparation environment and are unsupported. Binary regular files may be preserved, but
changed files must be UTF-8 text. Existing-file LF diffs only: no create/delete/rename,
binary patch, file mode or no-final-newline marker changes. Never rewrite a rejected patch
silently. Changes to tests, setup and configuration are outside the supported production
scope. The path filter is a conservative admission policy; ordinary tests can still be
influenced by the production code they execute.

Intake limits: GitHub reported repository size at most 20,000 KiB, 1,000 regular files,
1 MB per file, 8 MB total source, 8 MB compressed/16 MB expanded archive, 45 seconds total
fetch time. Patches are at most 64 KiB/four files/64 hunks per file. Request bodies are
bounded to 450,000 bytes. Paths use a conservative ASCII subset. Git export filters that
omit or rewrite tracked bytes are rejected when the archive fails tree verification.
Upstream redirects are rejected; renamed repositories must use their canonical identity.
GitHub's unauthenticated API availability/rate limits also apply.

## Actual execution boundary

The API only fetches, validates and persists inert bytes. The existing private evaluator
broker has Docker authority; it independently rebuilds admitted material and shares one
execution slot with historical evaluations. Candidate containers have no broker listener,
Docker socket, host binds, provider/database credentials or network. Docker proxy
configuration is explicitly not forwarded. The container uses UID/GID 1000, a read-only
root and source, dropped capabilities, no new privileges, 1 CPU, 512 MiB memory and swap
ceiling, 64 PIDs, 128 MiB scratch, 8 MiB tmp and 8 MiB shared memory. Individual files are
limited to 16 MiB. Docker logs are disabled; bounded command streams retain at most 64 KiB
per stream per command and mark truncation. Commands share an approved 1–120 second
wall-clock budget (default 45 seconds). Source preparation is bounded separately.

The broker checks Docker's actual settings before starting project commands. It polls the
same resource IDs through uncertain removals and requires confirmed cleanup before a test
result can be reported as passed. Restart cleanup reuses the inherited evaluator labels.
A Docker daemon outage can still delay or prevent cleanup; such failures retain an
infrastructure outcome, never a passing result. Do not run verification stacks concurrently
with active historical candidate environments because inherited restart cleanup is global
to those labels.

**Docker shares the host kernel and is not a complete defense against malicious code.**
The supported deployment is a trusted owner on a private machine; use a disposable VM for
adversarial repositories. There is no authentication for remotely exposing the privileged
stack. Never forward its ports or publish its broker. This milestone does not supply a
secure public arbitrary-code service.

## Records and interpretation

`repository-source-v1` stores the repository, immutable commit, recomputed Git tree,
SHA-256 file/tree identities, regular-file modes, full base bytes, fetch metadata and
upstream attribution. GitHub HTTPS commit metadata is the trust root for repository-to-
commit association. Archive file Git blob hashes and the complete Git tree are recomputed;
no Git checkout, filter, submodule initialization, hook or project import occurs.

`repository-candidate-v1` preserves exact submitted diff bytes/hash, explicitly approved
scope, original/modified text and all applied-source hashes. Its software identity binds
repository/base/source/applied bytes. User-declared authorship changes the import record,
not that software identity. `repository-plan-v1` binds that candidate and source to a
runtime image ID, working directory, exact setup/test arguments, offline dependency policy,
time budget, sandbox policy hash and test-scope description. Preparing a plan does not
approve it. Approval is saved with the exact candidate/plan and time at run admission.

Append-only source/candidate/plan rows have database immutability triggers. Every execution
gets a fresh UUID and retains the plan, full source/candidate material, engine identity,
actual image/container/initialized-source identities, observed Docker restrictions,
per-command arguments, start/end/duration, exit status and exact bounded output. Atomic
broker evidence and PostgreSQL state support cancellation and restart reconciliation.
Missing broker evidence becomes interruption/infrastructure failure; inconsistent evidence
is retained as unvalidated material. Completed results are validated again when reopened.

A zero test-command exit means only that the approved ordinary command succeeded.
Counts remain **unknown** in the API; people can inspect framework counts in exact output.
Setup failure, nonzero tests, timeout, cancellation, infrastructure failure and invalid
stored evidence remain distinct. Independent verification is always **not configured**.
There is no overall independently verified verdict, LLM log judgment, new model trial or
additional discovery counted from re-execution.

## Reproducible opt-in examples

The data-only [example manifest](../evaluation/repository-examples/g1/examples.json) declares
both repositories, immutable bases, patch sources, commands and expected outcomes before
execution. It is not an evaluator catalog. New repositories use the same APIs and require
no evaluator module changes. Normal CI uses synthetic offline source fixtures; real
GitHub validation is explicit and separate:

```sh
uv run --project backend python scripts/validate_repository_g1.py
# The first command prepares review material without execution.
uv run --project backend python scripts/validate_repository_g1.py --confirm-local-execution
uv run --project backend python scripts/browser_repository_g1.py --confirm-local-execution
```

The scripts default to the local API on port 8010 and retain artifacts under
`artifacts/repository-audit/external`. `--base-url http://127.0.0.1:18010` selects an isolated
local stack. Downloads include the full source and can be validated without refetching
GitHub. A new execution still requires importing/reviewing the exact base and patch and
approving an available runtime; a saved result is never replayed as a new pass.

[G1 engineering report](reports/GENERALIZED-PATCH-AUDIT-G01.md).
