# G2 observation-integrity correction evidence

These are authored regression fixtures for the specific review finding, not a benchmark or new defect discovery. The six JSON execution records use the corrected pinned Node 22 runtime, fresh control validation and test-owned approvals. Their real Docker runtime/source/verifier identities, timestamps, commands, observations and confirmed cleanup are retained. Fixture approval metadata is synthetic; this is not a captured human UI session.

`actual-adapter-comparison.json` executes both shipped adapter versions with the supplied review programs offline. Retired-version execution here is an explicit test-only characterization, not an admitted new production run. `reviewed-adapter-failure.log` retains the original four regression failures.

`api-history-audit.json` proves eight original records/downloads remained identical, retired execution and stale validation received HTTP 409, and no scalar demonstration was re-executed. Original G2 artifacts and their manifest were left unchanged in the sibling generalized-patch-audit-g02 directory. Only the pinned shipped archive is trusted for historical inspection.

`completion-audit.json` resolves the exact six runs and identities. The SHA256 manifest covers retained files except itself. Full-suite and CI logs are appended only as new correction evidence, never substituted into old execution records.
