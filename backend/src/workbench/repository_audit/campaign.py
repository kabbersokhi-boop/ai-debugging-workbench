"""Bounded campaign accounting over the existing validated audit evidence, never a scorer."""

import gzip
import json
from collections import Counter
from pathlib import Path

from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit.service import validate_saved
from workbench.repository_audit.verification import Requirement


def retained_campaign(root: Path):
    """Read only the registered, hashed downloads; never trust a manually entered scorecard."""
    declaration, cases, campaign_hash = load_campaign(root)
    index = json.loads((root / "results/index.json").read_text())
    if index["campaign_sha256"] != campaign_hash:
        raise ValueError("Retained results belong to another campaign")
    audits = {}
    for entry in index["entries"]:
        filename = entry["file"]
        if Path(filename).name != filename or not filename.endswith(".json.gz"):
            raise ValueError("Invalid retained evidence path")
        audits[entry["run_id"]] = json.loads(
            gzip.decompress((root / "results" / filename).read_bytes())
        )
    assessments = json.loads((root / "results/adjudications.json").read_text())
    summary = summarize(
        root, declaration, cases, campaign_hash, index["entries"], audits, assessments
    )
    summary["cases"] = [
        {
            "key": c["key"],
            "repository": c["repository"],
            "base_commit": c["base_commit"],
            "revision": c["revision"],
            "provenance": c["provenance"],
            "requirement": c["requirement"],
        }
        for c in cases
    ]
    return summary, audits


def load_campaign(root: Path):
    raw = (root / "campaign.json").read_bytes()
    expected = (root / "campaign.sha256").read_text().strip()
    if digest(raw) != expected:
        raise ValueError("Frozen campaign declaration changed")
    declaration = json.loads(raw)
    for name, checksum in declaration["files"].items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or digest(target.read_bytes()) != checksum:
            raise ValueError("Frozen campaign material changed: " + name)
    cases = json.loads((root / "cases.json").read_text())["cases"]
    if [c["key"] for c in cases] != declaration["case_order"]:
        raise ValueError("Campaign selection/order mismatch")
    patches = [digest((root / c["patch"]).read_bytes()) for c in cases]
    if len(set(patches)) != len(patches):
        raise ValueError("Duplicate genuine candidate patch")
    return declaration, cases, expected


def bind_audit(root, case, audit, role, declaration):
    """Validate downloaded evidence, then bind it to the predeclared material."""
    if audit["status"] == "invalid_evidence":
        raise ValueError("Invalid saved evidence")
    e = audit["evidence"]
    validate_saved(e, audit["id"])
    s, c, p, v = e["snapshot"], e["candidate"], e["plan"], e["verification"]["plan"]
    patch = (
        case["alternative_patch"]
        if role in ("alternative", "alternative_control")
        else case["patch"]
    )
    if (
        s["repository"].lower() != case["repository"].lower()
        or s["base_commit"] != case["base_commit"]
        or c["patch"] != (root / patch).read_text()
        or audit["candidate_id"] != c["id"]
        or audit["plan_id"] != identity(p)
        or audit["status"] != e["result"]["status"]
    ):
        raise ValueError("Campaign candidate/source/outcome identity mismatch")
    for field, value in case["ordinary"].items():
        if p[field] != value:
            raise ValueError("Campaign ordinary plan changed")
    image = declaration["runtime_images"][case["runtime"]]
    if (
        p["runtime"] != case["runtime"]
        or p["image_id"] != image
        or p["working_directory"] != "."
        or v["runtime"] != case["runtime"]
        or v["image_id"] != image
        or v["module"] != case["module"]
        or v["export"] != case["export"]
        or v["verifier_version"] != declaration["verifier_version"]
        or v["adapter_hashes"] != declaration["adapter_hashes"]
        or v["setup"] != []
        or v["timeout_seconds"] != 30
    ):
        raise ValueError("Campaign verifier/runtime changed")
    requirement = Requirement.model_validate({"snapshot_id": s["id"], **case["requirement"]})
    expected_requirement = {"id": identity(requirement.model_dump()), **requirement.model_dump()}
    if e["verification"]["requirements"] != [expected_requirement]:
        raise ValueError("Campaign requirement identity mismatch")
    expected_assertions = [
        {
            "id": a["id"],
            "args": a["args"],
            "kwargs": a.get("kwargs", {}),
            "expected": a["expected"],
            "requirement_id": expected_requirement["id"],
        }
        for a in case["assertions"]
    ]
    if v["assertions"] != expected_assertions:
        raise ValueError("Campaign assertions changed")
    expected_stage = "validation" if role in ("control", "alternative_control") else "execution"
    if e["stage"] != expected_stage:
        raise ValueError("Control substituted for candidate execution")
    return e["result"]


def classify(result, adjudication=None):
    """Describe validated application outcomes. A mismatch alone is never a finding."""
    if result.get("stage") == "validation":
        return "control"
    ordinary = (result.get("ordinary") or {}).get("status", "not_run")
    independent = result.get("independent", {}).get("status", "not_run")
    if adjudication and adjudication["classification"] in (
        "invalid_check",
        "ambiguous",
        "unsupported_environment",
        "unsupported_source",
    ):
        return adjudication["classification"]
    if ordinary == "tests_failed":
        return "ordinary_failure"
    if ordinary == "tests_passed" and independent == "checks_passed":
        return "ordinary_pass_independent_pass"
    if ordinary == "tests_passed" and independent == "assertions_failed":
        if adjudication and adjudication["classification"] == "supported_historical_defect":
            return "supported_historical_defect"
        return "unresolved_disagreement"
    if independent in ("check_execution_failed", "verifier_preparation_failed"):
        return "unsupported_execution"
    return "infrastructure_or_incomplete"


def summarize(root, declaration, cases, campaign_hash, entries, audits, adjudications=None):
    """Unique candidates, repeated trials, controls and disagreements have separate counts."""
    adjudications = adjudications or {}
    case_map = {c["key"]: c for c in cases}
    slots, run_ids, environments = set(), set(), set()
    rows = []
    for entry in entries:
        key, role, trial, run_id = (entry[k] for k in ("case", "role", "trial", "run_id"))
        slot = (key, role, trial)
        if key not in case_map or role not in (
            "candidate",
            "reference",
            "alternative",
            "control",
            "alternative_control",
        ):
            raise ValueError("Unknown campaign case/role")
        if trial not in ((1, 2) if role == "candidate" else (1,)):
            raise ValueError("Undeclared campaign trial")
        if slot in slots or run_id in run_ids:
            raise ValueError("Duplicate campaign slot or execution")
        slots.add(slot)
        run_ids.add(run_id)
        audit = audits[run_id]
        if audit["id"] != run_id or identity(audit) != entry["audit_hash"]:
            raise ValueError("Missing or changed campaign download")
        result = bind_audit(root, case_map[key], audit, role, declaration)
        executions = [result.get("ordinary"), result.get("independent", {}).get("execution")]
        executions += [c["execution"] for c in result.get("controls", [])]
        for execution in executions:
            if execution and execution.get("container_id"):
                container = execution["container_id"]
                if container in environments:
                    raise ValueError("Campaign reused an execution environment")
                environments.add(container)
        assessment = adjudications.get(key)
        if assessment and not assessment.get("explanation"):
            raise ValueError("Unjustified adjudication")
        rows.append(
            {
                **entry,
                "repository": case_map[key]["repository"],
                "revision": case_map[key]["revision"],
                "ordinary": (result.get("ordinary") or {}).get("status", "not_run"),
                "independent": result.get("independent", {}).get("status", "not_run"),
                "classification": classify(result, assessment),
                "assessment": assessment,
            }
        )
    genuine = [r for r in rows if r["role"] == "candidate"]
    by_case = {c["key"]: [r for r in genuine if r["case"] == c["key"]] for c in cases}
    repeat_disagreements = []
    for key, trials in by_case.items():
        if len(trials) == 2:
            signatures = {(r["ordinary"], r["independent"]) for r in trials}
            observations = [
                audits[r["run_id"]]["evidence"]["result"]["independent"]["checks"] for r in trials
            ]
            if len(signatures) != 1 or observations[0] != observations[1]:
                repeat_disagreements.append(key)
    # Candidate-level counts require both declared repeats to agree. No cherry-picking a pass.
    outcomes = Counter()
    for key, trials in by_case.items():
        outcome = (
            adjudications.get(key, {}).get("classification", "incomplete")
            if len(trials) != 2
            else "repeat_disagreement"
            if key in repeat_disagreements
            else trials[0]["classification"]
        )
        outcomes[outcome] += 1
    return {
        "version": "g3-evidence-summary-v1",
        "campaign_sha256": campaign_hash,
        "scope": declaration["scope"],
        "limitations": declaration["limitations"],
        "counts": {
            "selected_candidates": len(cases),
            "genuine_candidates_executed": sum(bool(v) for v in by_case.values()),
            "genuine_candidates_admitted": len(
                {r["case"] for r in rows if r["role"] in ("control", "reference", "candidate")}
            ),
            "planned_candidate_audits": 2 * len(cases),
            "candidate_audits": len(genuine),
            "control_validations": sum(
                r["role"] in ("control", "alternative_control") for r in rows
            ),
            "reference_audits": sum(r["role"] == "reference" for r in rows),
            "alternative_audits": sum(r["role"] == "alternative" for r in rows),
            "fresh_environments": len(environments),
            "repeat_disagreements": len(repeat_disagreements),
            "candidate_outcomes": dict(outcomes),
        },
        "rows": rows,
    }
