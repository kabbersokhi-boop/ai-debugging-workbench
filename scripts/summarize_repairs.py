"""Read-only summarization of the complete frozen comparison; refuses partial denominators."""

# ruff: noqa: E501 -- Markdown paragraphs and table rows preserve rendered output.
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config_path = ROOT / "evals/experiment-v2.json"
config = json.loads(config_path.read_text())
base = ROOT / "artifacts/evaluation-m4-v2"
if not (base / "evaluation-results.json").is_file():
    base = ROOT / "docs/reports/assets/milestone-04"
rows = json.loads((base / "evaluation-results.json").read_text())
expected = {
    (c["id"], method)
    for c in config["cases"]
    if c["split"] == "evaluation"
    for method in config["conditions"]
}
assert {(r["case"], r["condition"]) for r in rows} == expected and len(rows) == len(
    expected
), "Comparison is incomplete"
identity = hashlib.sha256(config_path.read_bytes()).hexdigest()
assert all(r["configuration_sha256"] == identity for r in rows)
summary = {
    "experiment": config["experiment"],
    "configuration_sha256": identity,
    "distinct_held_out_cases": 8,
    "condition_runs": len(rows),
    "budget": json.loads((base / "budget.json").read_text()),
    "conditions": {},
    "per_case": [],
}
for method in config["conditions"]:
    subset = [r for r in rows if r["condition"] == method]
    calls = [c for r in subset for c in r["provider_calls"]]
    usage = {
        k: sum(c.get("usage", {}).get(k, 0) for c in calls)
        for k in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    summary["conditions"][method] = {
        "cases": len(subset),
        "usable_candidates": sum(r["usable_candidate"] for r in subset),
        "issue_passed": sum(r["issue_passed"] for r in subset),
        "regression_passed": sum(r["regression_passed"] for r in subset),
        "final_passed": sum(r["final_passed"] for r in subset),
        "resolved": sum(r["resolved"] for r in subset),
        "statuses": {
            s: sum(r["status"] == s for r in subset)
            for s in sorted({r["status"] for r in subset})
        },
        "attempts": sum(r["attempts"] for r in subset),
        "model_http_calls": sum(r["model_calls"] for r in subset),
        "all_provider_http_attempts": len(calls),
        "tool_calls": sum(r["tool_calls"] for r in subset),
        "median_latency_ms": statistics.median(r["latency_ms"] for r in subset),
        "min_latency_ms": min(r["latency_ms"] for r in subset),
        "max_latency_ms": max(r["latency_ms"] for r in subset),
        "median_context_json_utf8_bytes": statistics.median(
            r.get("context_utf8_bytes", 0) for r in subset
        ),
        "available_usage": usage,
        "calls_with_usage": sum("usage" in c for c in calls),
        "calls_without_usage": sum("usage" not in c for c in calls),
    }
for r in rows:
    summary["per_case"].append(
        {
            k: r.get(k)
            for k in (
                "case",
                "condition",
                "usable_candidate",
                "issue_passed",
                "regression_passed",
                "final_passed",
                "resolved",
                "status",
                "attempts",
                "decisions",
                "model_calls",
                "tool_calls",
                "latency_ms",
                "context_utf8_bytes",
                "error",
            )
        }
    )
assets = ROOT / "docs/reports/assets/milestone-04"
assets.mkdir(parents=True, exist_ok=True)
(assets / "evaluation-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
lines = [
    "# Evaluation results",
    "",
    "## Frozen comparison",
    "",
    "**Eight distinct held-out synthetic defects, evaluated under three conditions (24 condition runs).** Four separate development cases were used before evaluation. No query paraphrases are counted as new defects. This is not a production debugging accuracy estimate.",
    "",
    f"Protocol: [`experiment-v2.json`](../evals/experiment-v2.json), SHA-256 `{identity}`; frozen before execution at `78989e3`. V1 was frozen but never executed; a pre-call deadline audit led to v2. No prompts, retrieval settings or model were tuned against these outcomes.",
    "",
    "Same NVIDIA model and settings: `"
    + config["model"]
    + "`, temperature 0, thinking disabled, 2,000 output tokens/request. Each condition receives the same report and original issue observation, with no prior AI diagnosis. Whole context contains all four target files. The loop conditions have six decisions/two patches; one-shot has one decision/patch. Only fixed feedback checks and validation errors can inform revisions. Sealed final checks run after termination and never enter model context.",
    "",
    "| Condition | Usable candidate | Issue check | All feedback checks | Sealed final checks | Resolved | Median elapsed | Model HTTP calls | All provider attempts |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
]
for method, s in summary["conditions"].items():
    lines.append(
        f"| {method} | {s['usable_candidates']}/8 | {s['issue_passed']}/8 | {s['regression_passed']}/8 | {s['final_passed']}/8 | {s['resolved']}/8 | {s['median_latency_ms'] / 1000:.2f}s | {s['model_http_calls']} | {s['all_provider_http_attempts']} |"
    )
lines += [
    "",
    "A resolution requires the issue check, every feedback regression check and every sealed final check to pass for the final candidate. Invalid output, provider failures, timeouts and infrastructure errors remain unresolved in these denominators. A feedback-verified status alone is not the final benchmark score. Candidate bytes, source, verifier/scoring code, scenario contract and actual runtime identities are retained.",
    "",
    "## Per-case outcomes",
    "",
    "| Defect | Condition | Outcome | Final score | Attempts | Model / tool calls | Elapsed |",
    "| --- | --- | --- | --- | --- | --- | --- |",
]
for r in rows:
    lines.append(
        f"| {r['case']} | {r['condition']} | {r['status']} | {'passed' if r['resolved'] else 'unresolved'} | {r['attempts']} | {r['model_calls']} / {r['tool_calls']} | {r['latency_ms'] / 1000:.2f}s |"
    )
lines += [
    "",
    "## Resource accounting",
    "",
    f"The transport admitted **{summary['budget']['http_requests']}/256 HTTP attempts** and reserved **{summary['budget']['reserved_output_tokens']:,}/256,000 output tokens** before sending requests. Failures/retries consume the same finite ledger. The persisted 90-minute deadline caps resumed processes and each condition has at most 300 seconds. Reservations are limits, not measured usage or billing.",
    "",
    "| Condition | Median supplied context JSON bytes | Available prompt tokens | Available completion tokens | Available total tokens | Usage-bearing calls / all calls |",
    "| --- | --- | --- | --- | --- | --- |",
]
for method, s in summary["conditions"].items():
    u = s["available_usage"]
    lines.append(
        f"| {method} | {s['median_context_json_utf8_bytes']:.0f} | {u['prompt_tokens']:,} | {u['completion_tokens']:,} | {u['total_tokens']:,} | {s['calls_with_usage']}/{s['all_provider_http_attempts']} |"
    )
lines += [
    "",
    "Provider usage is measured only where returned. Embedding/reranking workloads are included in all-provider accounting. Dollar cost is **unavailable**, not estimated. Latency includes original checks, candidate startup/verification, sealed scoring and cold indexing where applicable; fixed condition order and shared-host noise limit latency interpretation.",
    "",
    "## Interpretation and limitations",
    "",
    "All three conditions resolved 8/8 cases. Neither iteration nor retrieval improved the resolution count here. Retrieval supplied less initial context (median 3,776 versus 15,431 JSON bytes), but its additional source decisions and retrieval workloads increased total measured usage. Fixed condition order and original-check cache reuse make elapsed-time differences descriptive, not a causal speed comparison.",
    "",
    "This tiny related-source suite cannot establish general debugging ability, a production resolution rate, or robustness to arbitrary repositories. The defects are implementation variants of one synthetic retail application. Whole-target context fits the model input bound, making it a strong simple baseline. Raw denominators above are authoritative; retrieval or iteration should not be credited with an improvement when the baseline resolves the same cases.",
    "",
    "The original Milestone 2 eight-query retrieval smoke suite covered one defect: mean lexical recall@5 was 1.000 over six labeled queries, versus 0.833 for hybrid plus reranking. Those queries are not eight defects. Reuse [the original measured report](reports/MILESTONE-02.md) and its raw suite rather than treating this as a new retrieval benchmark.",
    "",
    "Reproduce with the committed protocol and retained exact runtime images. A different image is a new experiment identity, not proof from an old pass. If exact images are unavailable on another host, freeze a new explicitly versioned replication with `--experiment evals/experiment-v3.json --output artifacts/evaluation-m4-v3 --freeze`, commit it, then run the same live command with those arguments. Retain v2; the same held-out cases are no longer untouched in a replication.",
    "",
    "[Machine-readable summary](reports/assets/milestone-04/evaluation-summary.json) · [all raw condition records](reports/assets/milestone-04/evaluation-results.json) · [protocol](../evals/README.md) · [engineering report](reports/MILESTONE-04.md).",
]
(ROOT / "docs/RESULTS.md").write_text("\n".join(lines) + "\n")
print(json.dumps(summary["conditions"], indent=2))
