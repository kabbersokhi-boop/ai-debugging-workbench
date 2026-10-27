# Retained saved-validation follow-up

These real API/browser reports use implementation
`f59b3b1d3b8feba9ea8feb8bda0d4e8fabf5c552`. Its CI passed. The subsequent local full rerun
failed one browser test before execution-plan approval because runtime discovery had not
finished; see `local-runtime-discovery-race.log`. It was **72 passed, 1 failed, 4 skipped**.
This is a product/UI readiness failure, not a patch defect or independent discovery.

The final implementation waits for the selected runtime identity and strengthens the browser
regression with a deliberately delayed response. Final evidence is in `../final/`.
This directory preserves the earlier evidence; its reports are not relabeled as final runs.

The intermediate completion audit is retained as captured. The final report relies on the
separate `../final/completion-evidence-audit.json`, captured after the final full recovery cycle,
for the after-recovery claim.
