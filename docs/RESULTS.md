# Evaluation results

## Frozen comparison

**Eight distinct held-out synthetic defects, evaluated under three conditions (24 condition runs).** Four separate development cases were used before evaluation. No query paraphrases are counted as new defects. This is not a production debugging accuracy estimate.

Protocol: [`experiment-v2.json`](../evals/experiment-v2.json), SHA-256 `e4b319b0881395f940e2828bba8a179be0195e4a6e01c0d084aa78c6a176d138`; frozen before execution at `78989e3`. V1 was frozen but never executed; a pre-call deadline audit led to v2. No prompts, retrieval settings or model were tuned against these outcomes.

Same NVIDIA model and settings: `nvidia/nemotron-3.5-super-vl-120b-a12b`, temperature 0, thinking disabled, 2,000 output tokens/request. Each condition receives the same report and original issue observation, with no prior AI diagnosis. Whole context contains all four target files. The loop conditions have six decisions/two patches; one-shot has one decision/patch. Only fixed feedback checks and validation errors can inform revisions. Sealed final checks run after termination and never enter model context.

| Condition | Usable candidate | Issue check | All feedback checks | Sealed final checks | Resolved | Median elapsed | Model HTTP calls | All provider attempts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| one-shot-whole | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 28.60s | 9 | 9 |
| loop-whole | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 20.13s | 8 | 8 |
| loop-retrieval | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 38.49s | 16 | 64 |

A resolution requires the issue check, every feedback regression check and every sealed final check to pass for the final candidate. Invalid output, provider failures, timeouts and infrastructure errors remain unresolved in these denominators. A feedback-verified status alone is not the final benchmark score. Candidate bytes, source, verifier/scoring code, scenario contract and actual runtime identities are retained.

## Per-case outcomes

| Defect | Condition | Outcome | Final score | Attempts | Model / tool calls | Elapsed |
| --- | --- | --- | --- | --- | --- | --- |
| line-amount | one-shot-whole | verified | passed | 1 | 1 / 2 | 28.25s |
| line-amount | loop-whole | verified | passed | 1 | 1 / 2 | 20.00s |
| line-amount | loop-retrieval | verified | passed | 1 | 2 / 3 | 34.73s |
| total-sign | one-shot-whole | verified | passed | 1 | 1 / 2 | 29.56s |
| total-sign | loop-whole | verified | passed | 1 | 1 / 2 | 26.45s |
| total-sign | loop-retrieval | verified | passed | 1 | 2 / 3 | 41.52s |
| empty-shipping | one-shot-whole | verified | passed | 1 | 1 / 2 | 37.72s |
| empty-shipping | loop-whole | verified | passed | 1 | 1 / 2 | 19.90s |
| empty-shipping | loop-retrieval | verified | passed | 1 | 2 / 3 | 37.69s |
| single-free | one-shot-whole | verified | passed | 1 | 1 / 2 | 28.34s |
| single-free | loop-whole | verified | passed | 1 | 1 / 2 | 19.49s |
| single-free | loop-retrieval | verified | passed | 1 | 2 / 3 | 39.30s |
| increment-skip | one-shot-whole | verified | passed | 1 | 1 / 2 | 28.55s |
| increment-skip | loop-whole | verified | passed | 1 | 1 / 2 | 20.25s |
| increment-skip | loop-retrieval | verified | passed | 1 | 2 / 3 | 36.48s |
| add-reset | one-shot-whole | verified | passed | 1 | 1 / 2 | 28.52s |
| add-reset | loop-whole | verified | passed | 1 | 1 / 2 | 18.65s |
| add-reset | loop-retrieval | verified | passed | 1 | 2 / 3 | 53.47s |
| clamp-upper | one-shot-whole | verified | passed | 1 | 1 / 2 | 28.65s |
| clamp-upper | loop-whole | verified | passed | 1 | 1 / 2 | 24.39s |
| clamp-upper | loop-retrieval | verified | passed | 1 | 2 / 3 | 42.24s |
| invalid-default | one-shot-whole | verified | passed | 1 | 2 / 2 | 63.16s |
| invalid-default | loop-whole | verified | passed | 1 | 1 / 2 | 27.16s |
| invalid-default | loop-retrieval | verified | passed | 1 | 2 / 3 | 33.81s |

## Resource accounting

The transport admitted **81/256 HTTP attempts** and reserved **66,000/256,000 output tokens** before sending requests. Failures/retries consume the same finite ledger. The persisted 90-minute deadline caps resumed processes and each condition has at most 300 seconds. Reservations are limits, not measured usage or billing.

| Condition | Median supplied context JSON bytes | Available prompt tokens | Available completion tokens | Available total tokens | Usage-bearing calls / all calls |
| --- | --- | --- | --- | --- | --- |
| one-shot-whole | 15431 | 57,156 | 3,094 | 60,250 | 8/9 |
| loop-whole | 15431 | 57,156 | 3,041 | 60,197 | 8/8 |
| loop-retrieval | 3776 | 108,798 | 3,394 | 112,192 | 64/64 |

Provider usage is measured only where returned. Embedding/reranking workloads are included in all-provider accounting. Dollar cost is **unavailable**, not estimated. Latency includes original checks, candidate startup/verification, sealed scoring and cold indexing where applicable; fixed condition order and shared-host noise limit latency interpretation.

## Interpretation and limitations

All three conditions resolved 8/8 cases. Neither iteration nor retrieval improved the resolution count here. Retrieval supplied less initial context (median 3,776 versus 15,431 JSON bytes), but its additional source decisions and retrieval workloads increased total measured usage. Fixed condition order and original-check cache reuse make elapsed-time differences descriptive, not a causal speed comparison.

This tiny related-source suite cannot establish general debugging ability, a production resolution rate, or robustness to arbitrary repositories. The defects are implementation variants of one synthetic retail application. Whole-target context fits the model input bound, making it a strong simple baseline. Raw denominators above are authoritative; retrieval or iteration should not be credited with an improvement when the baseline resolves the same cases.

The original Milestone 2 eight-query retrieval smoke suite covered one defect: mean lexical recall@5 was 1.000 over six labeled queries, versus 0.833 for hybrid plus reranking. Those queries are not eight defects. Reuse [the original measured report](reports/MILESTONE-02.md) and its raw suite rather than treating this as a new retrieval benchmark.

Reproduce with the committed protocol and retained exact runtime images. A different image is a new experiment identity, not proof from an old pass. If exact images are unavailable on another host, freeze a new explicitly versioned replication with `--experiment evals/experiment-v3.json --output artifacts/evaluation-m4-v3 --freeze`, commit it, then run the same live command with those arguments. Retain v2; the same held-out cases are no longer untouched in a replication.

[Machine-readable summary](reports/assets/milestone-04/evaluation-summary.json) · [all raw condition records](reports/assets/milestone-04/evaluation-results.json) · [protocol](../evals/README.md) · [engineering report](reports/MILESTONE-04.md).
