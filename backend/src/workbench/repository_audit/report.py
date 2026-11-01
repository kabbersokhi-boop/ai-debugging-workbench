"""Readable reports derived exclusively from validated saved evidence."""

import json
import re


def block(value):
    # Long fences prevent untrusted repository prose from escaping evidence blocks.
    text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
    fence = "`" * max(3, max((len(s) for s in re.findall(r"`+", text)), default=0) + 1)
    return f"{fence}\n{text}\n{fence}"


def render_report(audit):
    e = audit["evidence"]
    result = e.get("result") or {}
    ordinary = (
        result.get("ordinary")
        if result.get("version")
        in {"repository-independent-result-v1", "repository-generated-result-v1"}
        else result
    )
    ordinary = ordinary or {}
    independent = result.get("independent") or {}
    lines = [
        "# Patch Audit report",
        "",
        f"Audit: {audit['id']}",
        f"Status: {audit['status']}",
        "Mode: saved evidence from local execution",
        "",
        "## Source and patch",
        block({k: e["snapshot"][k] for k in ("repository", "base_commit", "source_tree_hash")}),
        block(
            {
                "candidate_id": audit["candidate_id"],
                "candidate_hash": e["candidate"]["candidate_hash"],
                "affected_files": e["candidate"]["affected_files"],
            }
        ),
        "## Results",
        f"Selected existing tests: {ordinary.get('status', 'no completed evidence')}",
        f"Independent checks: {independent.get('status', 'not configured')}",
        "Passing applies only to declared checks and the approved environment.",
    ]
    if audit["status"] == "invalid_evidence":
        lines += ["Stored evidence failed validation. No passing conclusion is available."]
    if result.get("reason") or e.get("reason"):
        lines += [block(result.get("reason") or e.get("reason"))]
    if e.get("checklist_use"):
        use = e["checklist_use"]
        lines += [
            "## Reused project checklist",
            block(
                {
                    "id": use["checklist_id"],
                    "name": use["checklist"]["name"],
                    "revision": use["checklist"]["revision"],
                    "application": use["id"],
                }
            ),
        ]
    lines += [
        "## Approved execution plan",
        block(e["plan"]),
        "## Exact local approval",
        block(e["approval"]),
    ]
    verification = e.get("verification") or {}
    for index, req in enumerate(verification.get("requirements", []), 1):
        lines += [
            f"## Requirement {index}",
            "Required behavior:",
            block(req["statement"]),
            "Expected behavior:",
            block(req["expected_behavior"]),
            "Supported inputs:",
            block(req["input_domain"]),
            "Why this expectation is justified:",
            block(req["provenance"]["justification"]),
            "Supporting source:",
            block({k: req["provenance"][k] for k in ("origin", "reference", "excerpt")}),
            "Assumptions and ambiguities:",
            block({"assumptions": req["assumptions"], "ambiguities": req["ambiguities"]}),
        ]
    for check in independent.get("checks", []):
        declared = next(
            (
                a
                for a in verification.get("plan", {}).get("assertions", [])
                if a["id"] == check["id"]
            ),
            {},
        )
        lines += [
            "## Input, expected behavior and actual observation",
            block(
                {
                    "check": check["id"],
                    "status": check["status"],
                    "requirement_id": check["requirement_id"],
                }
            ),
            "Input:",
            block(
                check.get("input", {"args": declared.get("args"), "kwargs": declared.get("kwargs")})
            ),
            "Expected behavior:",
            block(check.get("expected", declared.get("expected"))),
            "Actual observation:",
            block(check["observed"] if "observed" in check else "No valid observation"),
        ]
        if check.get("error"):
            lines += ["Observation error:", block(check["error"])]
    if result.get("controls"):
        lines += [
            "Synthetic controls validate the checker adapter and named assertions. "
            "They do not establish that the specification is correct."
        ]
    for control in result.get("controls", []):
        lines += ["## Checker control", block(control)]
    for command in [
        *ordinary.get("commands", []),
        *(independent.get("execution") or {}).get("commands", []),
    ]:
        lines += ["## Command evidence", block(command)]
    if result.get("version") == "repository-generated-result-v1":
        lines += ["## Approved input generation", block(result["search"]), result["limitations"]]
        if result.get("counterexample"):
            case = result["counterexample"]
            lines += [
                "## Reproduced counterexample",
                "Input:",
                block(case["input"]),
                "Expected behavior:",
                block(case["expected"]),
                "Actual observation:",
                block(case["observed"]),
                "Original failing input:",
                block(case["original_input"]),
                "Reproduction declaration:",
                block(case["reproduction"]),
                "The retained failure was repeated in two fresh environments. "
                "Reduction is bounded and does not prove a globally smallest input.",
            ]
        for entry in result.get("generated_runs", []):
            lines += ["## Generated search/reduction/reproduction execution", block(entry)]
    lines += [
        "## Inspect and reproduce",
        "Reopening this audit does not execute it again. "
        "Keep the complete JSON evidence alongside this report.",
        f"Evidence: /api/repository-audits/runs/{audit['id']}/evidence",
        f"Patch: /api/repository-audits/candidates/{audit['candidate_id']}/patch",
        "For fresh execution, import the pinned source and exact patch locally, review the plans, "
        "validate fresh controls and explicitly approve each exact execution.",
    ]
    return "\n\n".join(line for line in lines if line) + "\n"
