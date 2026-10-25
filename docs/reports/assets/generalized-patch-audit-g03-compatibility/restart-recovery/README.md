# PR #15 restart recovery correction evidence

This add-on concerns coordinator engineering only. The original G3 and Node addendum
campaign inputs/results remain frozen; no campaign execution was repeated.

- `workflow-comparison.json` binds the original failed/passing `compose.log` bytes,
  audit IDs, polling counts and available lifecycle observations. The two original
  service logs are retained here. They lack per-request timestamps and a DB dump;
  reconstructed DB mutations come from the original integration scenario.
- `causal-reproduction.py` uses public asyncio/AnyIO APIs to control the cancellation
  race in the legacy polling body. `causal-result.json` records an expired timeout
  with continued polling and a pending native cancellation. It then cleans up its
  own task. It does not claim to recover the exact original CI scheduling.
- `focused.log` and `check.log` record 13 focused recovery regressions and the complete
  358-test offline/static/build gate at implementation
  `dbc59678289e9b772605206a14839253273954eb`.
- `restart-plan.json` was committed before the five real trials. `trials.json`
  journals every attempt, implementation/container/image/audit identities, completed
  evidence hashes, execution submission counts and actual resource-absence checks.
  `trial-summary.json` extracts readiness, missing-result timing and poll counts.
  All five original-strength restart trials passed; none was replaced or repeated.
  Each `trial-N.log`, `trial-N-api.log` and `trial-N-evaluator.log` is retained.
- `restart-trials.py` is the exact local orchestration harness. It refuses to
  overwrite an existing trial journal. This is execution tooling, not a replay
  command; the authorized stress limit has already been reached.

The report and PR handoff distinguish the required complete suite, inherited restart
tests and recovery smoke from these five stress trials. Those engineering fixtures
use synthetic repositories/offline providers; they are not genuine G3 candidates or
real model inference. Legacy harness topology setup is recorded separately and its
original broker state is restored.

The final delivery adds documentation/evidence only after the tested implementation.
Actual final-head push and PR CI links, statuses and exact final SHA are in PR #15.
Do not interpret an earlier green run as validation of changed runtime code. The
original failed push run remains a failure, with no rerun to erase it.

`SHA256SUMS` covers this folder's review files relative to this directory. Hashes
identify content; they are not third-party signatures. The parent folder's older
manifest and historical evidence have not been rewritten.
