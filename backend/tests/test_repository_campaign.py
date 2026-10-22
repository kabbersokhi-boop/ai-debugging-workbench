"""Deterministic campaign accounting and freeze guards; no live upstream fetches."""

import copy
import json

import pytest

from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit import campaign


@pytest.mark.parametrize(
    "ordinary,independent,assessment,expected",
    [
        ("tests_failed", "assertions_failed", None, "ordinary_failure"),
        ("tests_failed", "checks_passed", None, "ordinary_failure"),
        ("tests_passed", "checks_passed", None, "ordinary_pass_independent_pass"),
        ("tests_passed", "assertions_failed", None, "unresolved_disagreement"),
        ("tests_passed", "assertions_failed", "invalid_check", "invalid_check"),
        ("tests_passed", "assertions_failed", "ambiguous", "ambiguous"),
        (
            "tests_passed",
            "assertions_failed",
            "supported_historical_defect",
            "supported_historical_defect",
        ),
        ("tests_passed", "check_execution_failed", None, "unsupported_execution"),
        ("infrastructure_error", "not_run", None, "infrastructure_or_incomplete"),
    ],
)
def test_conclusions_require_the_correct_evidence_layer(
    ordinary, independent, assessment, expected
):
    result = {"ordinary": {"status": ordinary}, "independent": {"status": independent}}
    adjudication = {"classification": assessment} if assessment else None
    assert campaign.classify(result, adjudication) == expected
    assert campaign.classify({**result, "stage": "validation"}) == "control"


def frozen(root):
    (root / "a.patch").write_text("first")
    (root / "b.patch").write_text("second")
    cases = [{"key": "a", "patch": "a.patch"}, {"key": "b", "patch": "b.patch"}]
    (root / "cases.json").write_text(json.dumps({"cases": cases}))
    declaration = {
        "case_order": ["a", "b"],
        "files": {p.name: digest(p.read_bytes()) for p in root.iterdir()},
    }
    raw = json.dumps(declaration).encode()
    (root / "campaign.json").write_bytes(raw)
    (root / "campaign.sha256").write_text(digest(raw))
    return declaration, cases


def test_frozen_manifest_and_material_cannot_change(tmp_path):
    frozen(tmp_path)
    campaign.load_campaign(tmp_path)
    (tmp_path / "a.patch").write_text("changed")
    with pytest.raises(ValueError, match="material changed"):
        campaign.load_campaign(tmp_path)
    (tmp_path / "campaign.json").write_text("{}")
    with pytest.raises(ValueError, match="declaration changed"):
        campaign.load_campaign(tmp_path)


def test_duplicate_patches_are_not_distinct_genuine_candidates(tmp_path):
    frozen(tmp_path)
    (tmp_path / "b.patch").write_text("first")
    declaration = json.loads((tmp_path / "campaign.json").read_text())
    declaration["files"]["b.patch"] = digest(b"first")
    raw = json.dumps(declaration).encode()
    (tmp_path / "campaign.json").write_bytes(raw)
    (tmp_path / "campaign.sha256").write_text(digest(raw))
    with pytest.raises(ValueError, match="Duplicate genuine"):
        campaign.load_campaign(tmp_path)


def accounting(monkeypatch, tmp_path, roles=("candidate", "candidate", "control", "alternative")):
    cases = [{"key": "a", "repository": "fixture/a", "revision": "a" * 40}]
    declaration = {"scope": "synthetic accounting fixture", "limitations": ["not a real trial"]}
    entries, audits = [], {}
    for i, role in enumerate(roles):
        trial = 2 if i == 1 and role == "candidate" else 1
        run_id = str(i)
        audits[run_id] = {
            "id": run_id,
            "evidence": {
                "result": {
                    "ordinary": {"status": "tests_passed", "container_id": "o" + str(i)},
                    "independent": {"status": "checks_passed", "checks": [{"observed": 3}]},
                }
            },
        }
        entries.append(
            {
                "case": "a",
                "role": role,
                "trial": trial,
                "run_id": run_id,
                "audit_hash": identity(audits[run_id]),
            }
        )
    # Identity/semantic binding has dedicated replay tests; here isolate aggregation invariants.
    monkeypatch.setattr(campaign, "bind_audit", lambda r, c, a, k, d: a["evidence"]["result"])
    return declaration, cases, entries, audits


def test_controls_references_and_repeats_do_not_inflate_candidate_metrics(monkeypatch, tmp_path):
    d, cases, entries, audits = accounting(monkeypatch, tmp_path)
    result = campaign.summarize(tmp_path, d, cases, "hash", entries, audits)
    assert result["counts"]["genuine_candidates_executed"] == 1
    assert result["counts"]["candidate_audits"] == 2
    assert result["counts"]["control_validations"] == 1
    assert result["counts"]["alternative_audits"] == 1
    assert result["counts"]["candidate_outcomes"] == {"ordinary_pass_independent_pass": 1}
    with pytest.raises(ValueError, match="Duplicate campaign"):
        campaign.summarize(tmp_path, d, cases, "hash", entries + [entries[0]], audits)


def test_missing_tampered_and_repeated_environment_evidence_rejected(monkeypatch, tmp_path):
    d, cases, entries, audits = accounting(monkeypatch, tmp_path)
    with pytest.raises(KeyError):
        campaign.summarize(tmp_path, d, cases, "hash", entries, {})
    changed = copy.deepcopy(audits)
    changed["0"]["id"] = "another"
    with pytest.raises(ValueError, match="changed campaign download"):
        campaign.summarize(tmp_path, d, cases, "hash", entries, changed)
    audits["1"]["evidence"]["result"]["ordinary"]["container_id"] = "o0"
    entries[1]["audit_hash"] = identity(audits["1"])
    with pytest.raises(ValueError, match="reused an execution environment"):
        campaign.summarize(tmp_path, d, cases, "hash", entries, audits)


def test_changed_observations_and_missing_repeats_cannot_be_accepted(monkeypatch, tmp_path):
    d, cases, entries, audits = accounting(monkeypatch, tmp_path)
    audits["1"]["evidence"]["result"]["independent"]["checks"] = [{"observed": 4}]
    entries[1]["audit_hash"] = identity(audits["1"])
    result = campaign.summarize(tmp_path, d, cases, "hash", entries, audits)
    assert result["counts"]["repeat_disagreements"] == 1
    assert result["counts"]["candidate_outcomes"] == {"repeat_disagreement": 1}
    result = campaign.summarize(tmp_path, d, cases, "hash", entries[:1], audits)
    assert result["counts"]["candidate_outcomes"] == {"incomplete": 1}
