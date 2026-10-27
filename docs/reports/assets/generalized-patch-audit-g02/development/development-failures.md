# Retained G2 development failures

Initial static validation: Ruff caught formatting/import issues; Pyright caught the Python adapter treating a module as a callable. Corrected formatting and explicitly typed the resolved public callable.

Initial targeted offline run: **25 failed, 83 passed in 1.66s**. All 25 G2 failures occurred before exercising assertions: the new fixture passed runtime twice to the inherited `plan_for` helper (`TypeError: Plan() got multiple values for keyword argument runtime`). The 83 G1 tests passed. Corrected only the new fixture to override the returned plan dictionary; no assertions relaxed.

First browser attempt: 1 failure, approval control not visible after 60 seconds. It overlapped the external trial on the single-capacity broker; no browser validation run was admitted. Retained raw failure, and added an explicit HTTP 202 admission assertion to distinguish API rejection from UI polling failures. Subsequent execution is serialized with external demonstrations.

First complete acceptance run at 94a4d88: **81 passed, 1 failed, 4 skipped, 234 deselected**, 643.50 seconds. G1 browser strict-mode selection of the sole checkbox became ambiguous after adding the independent-verification option. Corrected the browser test and optional G1 reproduction script to select the exact existing execution-approval label. Product behavior and result assertions were not relaxed. CI push run 39327820745 and PR run 39327857377 retained the same failure.

CI at 013c588 failed before integration: `ubuntu-latest` resolved to Ubuntu 26.04, unsupported by pinned Playwright 1.58.0 (`ERROR: Playwright does not support chromium on ubuntu26.04-x64`). Both CI jobs reproduced this host-image drift. Pinned the workflow to Ubuntu 24.04, consistent with the existing Playwright Noble container. No browser tests, assertions, runtime pins or sandbox restrictions were weakened. Raw sanitized job log retained as ci-browser-install-failure.log.

Second complete local run: **81 passed, 1 failed, 4 skipped, 234 deselected**, 733.21 seconds. The G1 browser execution received a genuine infrastructure_error before any test command: source initializer removal was not confirmed within the existing 20-second cleanup deadline. Final cleanup subsequently confirmed both container and volume absent. Raw terminal evidence retained in e2e-infrastructure-evidence.json; no pass was inferred and no limit/assertion was loosened. Supported-host CI run 39819939542 passed the complete same-code workflow.
