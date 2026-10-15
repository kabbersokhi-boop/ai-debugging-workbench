# Evidence ledger

- `evaluation-results.json`: all 24 real-provider held-out condition records, including model inputs/raw output, candidates, MCP actions, identity and failed/retried provider attempts. `budget.json` is the admitted transport ledger; reservations are not billing.
- `evaluation-summary.json`: read-only aggregation produced by `scripts/summarize_repairs.py`; the script rejects incomplete or mismatched denominators.
- `evaluation/<case>--<condition>/final-checks.json` and `final.png`: evaluation-only checks after termination, bound to exact served candidate bytes, source/scenario, scoring code and runtime. RAG conditions also retain `retrieval.json`. These files never enter runtime retrieval or model feedback.
- `live-*.json`: four separate actual product workflows on the development split. The first shipping browser acceptance exposed a UI lifecycle error after the backend verified its candidate; `m4-live-workflow.txt` retains that failure. `live-engine-binding.json` records actual capture-image/source coverage. No model proposal was manually fixed.
- `final-shipping-*.png` and `m4-reopen-browser.txt`: interaction with that saved actual candidate after the UI correction. Reopening makes no new inference. The captioned video in `docs/demo/` comes from this saved-run capture.
- `remote-timeout-record.json`: actual deterministic offline malicious-script probe, not an NVIDIA attempt. Its remote interaction was stopped and the environment removed; it has no completed verification pass.
- `m4-ci-first-failure.txt`: the first remote CI failure, retained alongside the preview replacement correction and deterministic delayed-response regression.
- `preservation.json` / `m4-migration.txt`: historical row/artifact preservation and additive migration exercised on a disposable restored database.
- Final check, offline acceptance, release audit and browser logs identify the final tested image separately from older live evidence.

JSON records preserve actual sanitized structured evidence. Committed text transcripts strip trailing whitespace from tool output; outcomes/errors/timings are retained. Screenshots contain only the synthetic application. No provider key, authorization header, environment file, database dump or private user repository is included.
