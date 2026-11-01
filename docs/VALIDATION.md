# Verification and evidence

Patch Audit keeps the result of existing tests separate from additional behavior checks. A pass describes the selected inputs, requirements and environment; it is not proof that every behavior is correct.

## Automated checks

[GitHub Actions](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/workflows/ci.yml) runs the standard checks on each pull request to `main` and on `main` itself:

- Python tests, formatting, lint and type checking.
- The production frontend build.
- Complete browser and integration journeys, including prepared Python/Node audits, checklist reuse and terminal/browser equivalence.
- Generated-input failure detection, simplification and fresh reproduction.
- Database migrations, cancellation and crash recovery.
- The recorded viewer's execution restrictions and browser journeys.

Four model/demo tests are opt-in and stay skipped in standard CI. Standard verification needs no model credentials.

The [reference verified build](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/41305878763), at commit `9edc175af57556f8c26ef1ce46f399e1415ca43d`, passed **457 offline tests, 110 integration/browser tests with four opt-in skips, and three separate recorded-viewer browser tests** in complete runs. Consult the current workflow for newer source; those numbers describe that specific build.

## Downloadable CI evidence

The `patch-audit-review-evidence` artifact contains a bounded package with:

- An intentionally faulty Python example, its simplified failing input and a separately approved replay.
- Python and Node checklist comparisons, result observations and report/patch export hashes.
- Desktop/mobile screenshots, JUnit results and relevant test logs.
- Migration, recovery and recorded-container checks.
- The tested commit, a file manifest and SHA-256 checksums.

The package fails validation if a required file is missing. It includes fixed public examples and deliberately faulty test cases; it excludes environment files, private history and database dumps. CI artifacts are retained for 14 days. [Reference artifact](https://github.com/kabbersokhi-boop/ai-debugging-workbench/actions/runs/41305878763/artifacts/13084020030).

Source, tests and frozen research inputs remain in the repository after an artifact expires. [Historical verification records](https://github.com/kabbersokhi-boop/ai-debugging-workbench/tree/9edc175af57556f8c26ef1ce46f399e1415ca43d/docs/reports) retain earlier results and failed attempts.

## What has and has not been shown

The [Boltons case study](PATCH-AUDIT-CASE-STUDY.md) shows one saved AI-generated repair that passed 155 selected tests but missed a second implementation. That is separate from the six-patch historical developer study, where additional checks found no defects beyond the one already caught by existing tests.

Generated-input examples demonstrate the checking mechanism using deliberately faulty code. They are not newly discovered AI failures. Two fresh reproductions support the retained example, not a universal correctness claim or a guarantee of the smallest possible input.

Unassisted setup time, comprehension and broader usefulness have not been measured with unfamiliar developers. The [user-testing guide](PATCH-AUDIT-USABILITY-SESSION.md) describes how to collect those observations. No general detection rate, model ranking or measured usability improvement is claimed.

## Reproduce checks locally

Follow the [quickstart](PATCH-AUDIT-QUICKSTART.md) to build the local application.
Install the development dependencies and browser before running the checks:

```sh
uv sync --project backend --frozen
npm ci --prefix frontend
uv run --project backend playwright install --with-deps chromium
./scripts/check
./scripts/e2e
./scripts/recovery-smoke
```

Use the separate [recorded-viewer build](RELEASE.md) for its container and browser checks. Never run candidate code directly on the host or expose the local execution services publicly.
