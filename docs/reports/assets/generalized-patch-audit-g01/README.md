# G1 retained verification evidence

These are fresh local executions of implementation
`771d544490ad8c00e3b74d5c2e579a00cb2dcff6`, with public MIT upstream source and synthetic
application data. Exact upstream source/license bytes are embedded in the evidence JSON.

- `python.json`, `node.json`, `node-regression.json`: actual API executions.
- `*-browser.json`: separate browser executions of the same candidates, not new discoveries.
- `*-review.png`, `*-result.png`: actual public-repository review/result screenshots.
- `external-execution-index.json`: source, patch, candidate, plan, runtime and execution IDs.
- `completion-evidence-audit.json`: final validation, downloads and reopen after recovery,
  with actual container/volume absence checked.
- `preservation.json`: unchanged historical files and actual API/broker source identity.
- `repository-recovery.json`, `debugger-recovery.json`: actual recovery checks.
- `recorded-boundary.json`: actual restricted recorded-container audit.
- `ci-implementation.json`: successful GitHub implementation CI reference.
- Logs are actual check, e2e, recovery, release and real GitHub/browser outputs.
- `development-invalid-browser-evidence.json` retains the earlier failed browser attempt
  caused by uncertain Docker removal. It is invalid evidence and is never counted as a pass.

The report describes all outcomes and limitations. `manifest.json` hashes every selected asset;
it excludes itself. No private credential, model conversation or environment file is included.
