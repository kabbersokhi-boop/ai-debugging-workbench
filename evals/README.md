# Bounded retail evaluation

Twelve implementation defects span pricing, shipping, quantity transitions and input bounds. Four are development/demo cases; eight are held out. `scenarios-v1.json` records the split. Reports are symptoms, not reference patches. Each variant changes executable source; query paraphrases are not counted as defects.

Runtime ingestion reads exactly four target files from approved immutable manifests. `evals/`, trusted verification, historical reports, recordings and reference controls are outside that corpus. `final_checks.py` is not copied into runtime images and runs only after the last candidate. Its results never reach a repair prompt. The ordinary 12 browser checks and patch-validation errors are available as loop feedback.

## Protocol

1. Validate the development cases and runtime boundaries.
2. Freeze with `uv run --project backend python scripts/evaluate_repairs.py --freeze` and commit the generated `experiment-v2.json` **before** held-out execution.
3. Run `uv run --project backend python scripts/evaluate_repairs.py --live --split evaluation`.

The harness refuses changed source/configuration/runtime identities. It uses the existing NVIDIA model, temperature zero, disabled thinking and 2,000 output tokens. Conditions are one-shot whole-target, bounded loop whole-target, and bounded loop with the existing hybrid/reranking strategy. All receive the same report and original browser observation; none receives a prior AI diagnosis. Whole-context conditions still have the same bounded MCP source tools. One-shot has one decision/patch and no revision feedback. Each loop has six decisions/two patches. Runtime repair still uses native PostgreSQL checkpoints; benchmark runs use the same graph with an in-memory saver and atomically retain every completed state and rejected raw output on disk.

The experiment has **256 HTTP requests including retries, 256,000 reserved output tokens, 90 minutes**, and 300 seconds per condition. The HTTP transport charges the persisted ledger before each request. Failed requests are charged. A single decision can have the configured transient retry, within its request bound. Four product development/demo workflows have a separate maximum of 80 provider requests (12 diagnosis + 8 repair each); no open-ended tuning campaign is authorized by this protocol.

Final-candidate scoring requires the scenario's issue check, every feedback regression check and every evaluation-only final check to pass. Invalid outputs, timeouts, provider failures and infrastructure errors remain unresolved in the denominator. Earlier attempts remain in resource accounting. Partial records are retained, not corrected into model successes. Context sizes, original/candidate/runtime identities, model/tool calls, latency and available provider usage accompany each condition. Latency includes cold retrieval indexing where applicable; there is no claim that a tiny synthetic suite estimates production accuracy. Dollar cost is unavailable.

The previous eight-query retrieval smoke measurements remain in the Milestone 2 report; they did not establish a retrieval advantage. They are not twelve independent bugs and are not rerun to favor a method here.

If an implementation correction is needed after held-out execution, retain v1 and create a new versioned experiment. Never overwrite a failed experiment or tune a prompt against its outcomes.

Protocol v1 was frozen but never executed. A pre-execution audit found that resumed processes did not enforce the persisted wall deadline; v2 adds that guard and caps each condition to the remaining shared deadline. V1 remains in Git. No held-out outcome or provider call informed the correction.
