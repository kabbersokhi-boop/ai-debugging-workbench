# G3 Node compatibility review evidence

This folder contains engineering verification and sanitized screenshots of the two public
historical cases. The immutable experiment inputs and twelve original application downloads
remain in `evaluation/repository-examples/g3-node-compatibility`; original G3 is separate
and unchanged. `summary.json` derives from the application evidence validator.

`completion-audit.json` checks both preflights, all twelve audits, distinct environments,
actual resource absence and historical preservation. `history-runtime-audit.json` checks
served implementation bytes and exact saved/downloaded records after recovery. Reopening
saved evidence starts no new audit. `SHA256SUMS` identifies these review artifacts; hashes
provide content identity, not a third-party signature.

`check.log` records 345 passing offline tests. `ci-tested.json` records successful full
standard-topology CI at implementation `98a57bd3f91116e6cd3f18ef986e2301543195d7`,
including 91 integration tests, four existing live opt-in skips, recovery smoke, actual
recorded server and two recorded browsers. `ci-implementation-history.json` lists all four
implementation CI runs. Final report-head CI URLs and exact SHA are in PR #15's handoff.

The complete isolated local suite did not pass in one invocation. `development` retains
the initial 18-failure run (17 address-pool failures plus one legacy topology precondition),
service errors and task-network recovery. `e2e-local-isolated.log` retains the one full
rerun: 90 passed, one inherited harness topology failure, four existing opt-in skips.
`legacy-harness-test.log` records that unchanged test passing once with its expected broker;
`legacy-harness-check.json` proves source identity and restoration of its original stopped
state. `engineering-recovery.json` separates this setup work from zero campaign retries.
No unsuccessful semantic trial was replaced or erased. Other local logs record focused
capsule, browser, recovery and recorded-release checks; fixture/offline provider counters
are not real model inference and do not add genuine candidates.

The historical dependency requirement was `^1.0.0` without a lock. Pinned `array-flatten`
1.0.0 is an explicit compatible choice, not a recovered exact historical installation.
Registry integrity, capsule file identities and MIT attribution are retained in the repo.
All candidate execution was offline in restricted containers; saved replay is read-only.
