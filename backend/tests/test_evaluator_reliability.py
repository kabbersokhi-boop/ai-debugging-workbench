"""Deterministic fixtures, never producer evidence; live preflight is an explicit CLI command."""

import copy
import json

import pytest

from workbench.evaluator import reliability as v2
from workbench.evaluator import reliability_producer as p
from workbench.evaluator.catalog import candidate, digest, identity, task
from workbench.evaluator.experiment import assert_frozen, comparison, read_trial
from workbench.evaluator.experiment_catalog import freeze
from workbench.rag.provider import ProviderError

IMAGE = "sha256:" + "a" * 64


def phase(files, command, image, cancel):
    return {
        "command": command,
        "image_id": image,
        "container_id": "fixture-container",
        "executed_file_hashes": {k: digest(v) for k, v in files.items()},
        "status": "finished",
        "exit_code": 0,
        "duration_ms": 1,
        "stdout": "9 passed",
        "stderr": "",
    }


class Provider:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []
        self.payloads = []

    async def request(self, workload, url, payload):
        self.payloads.append(copy.deepcopy(payload))
        item = next(self.outputs)
        call = {"model": payload["model"], "attempt": 1, "latency_ms": 1}
        self.calls.append(call)
        if isinstance(item, Exception):
            if isinstance(item, ProviderError):
                call["status"] = 502
            else:
                call["error"] = type(item).__name__
            raise item
        body = (
            item
            if "choices" in item
            else {
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(item)}}],
                "model": "fixture-returned",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }
        )
        call["status"] = 200
        if isinstance(body.get("usage"), dict):
            call["usage"] = {
                k: v
                for k, v in body["usage"].items()
                if k in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
        return body


def actions():
    return [
        {"tool": "search", "query": "class bucket"},
        {"tool": "edit", "edits": candidate("more-bucket-reference")["edits"]},
        {"tool": "test"},
        {"tool": "submit"},
    ]


async def run(tmp_path, monkeypatch, outputs, executor=None):
    monkeypatch.setattr(p, "execute", executor or phase)
    f = v2.definition(True)
    coord = f["body"]["order"][0]
    f["body"]["image_id"] = IMAGE
    f["hash"] = identity(f["body"])
    provider = Provider(outputs)
    folder = tmp_path / "trial"
    campaign = p.Campaign(tmp_path / "campaign", create=True)
    await p.generate(
        task(coord["task_id"]),
        f["body"]["configurations"][coord["configuration_id"]],
        coord,
        f,
        folder,
        campaign,
        provider,
    )
    record = {
        "generation": json.loads((folder / "generation.json").read_text()),
        "events": [json.loads(path.read_text()) for path in sorted(folder.glob("event-*.json"))],
        "candidate": json.loads((folder / "candidate.json").read_text())
        if (folder / "candidate.json").exists()
        else None,
        "result": None,
        "scoring": None,
    }
    v2.validate(record, f)
    return record, f, provider


def test_historical_24_outcomes_and_freeze_remain_exact():
    f = freeze()
    assert f["hash"] == "aaf36a066a50e463e1a28a912353dec2c210ce887a439e54089183ffa547cdf4"
    assert_frozen(f)
    s = comparison([read_trial(c["id"]) for c in f["body"]["order"]], f, require_complete=True)
    assert s["attempted"] == 24
    assert [g["completed"] for g in s["groups"]] == [3, 3]
    assert sum(g["outcomes"]["infrastructure_or_provider_failure"] for g in s["groups"]) == 10
    assert sum(g["outcomes"]["no_usable_candidate"] for g in s["groups"]) == 8
    assert sum(g["incremental_numerator"] for g in s["groups"]) == 0


@pytest.mark.parametrize(
    "choice",
    [
        {
            "finish_reason": "length",
            "message": {"content": None, "reasoning_content": "x"},
            "usage": {"completion_tokens": 3000},
        },
        {"finish_reason": "stop", "message": {"content": None}},
        {"finish_reason": "length", "message": {"content": '{"tool":"submit"}'}},
    ],
)
def test_no_actions_from_truncated_or_null_content(choice):
    with pytest.raises(ValueError):
        p.decision({"choices": [choice]})


def test_declared_protocol_forms_and_supported_parameters():
    assert p.decision(
        {"choices": [{"finish_reason": "stop", "message": {"content": '{"tool":"submit"}'}}]}
    ) == {"tool": "submit"}
    assert p.decision(
        {
            "choices": [
                {"finish_reason": "stop", "message": {"content": '{"actions":[{"tool":"test"}]}'}}
            ]
        }
    ) == {"tool": "test"}
    cfg = list(v2.configurations().values())
    assert cfg[0]["parameters"] == cfg[1]["parameters"]
    assert cfg[0]["parameters"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "reasoning_budget" not in cfg[0]["parameters"]


async def test_real_protocol_lifecycle_and_feedback_before_submit(tmp_path, monkeypatch):
    record, f, provider = await run(tmp_path, monkeypatch, actions())
    assert record["generation"]["generation_status"] == "submitted"
    assert record["generation"]["counts"] == {
        "read_search_actions": 1,
        "revisions": 1,
        "ordinary_runs": 1,
    }
    assert "9 passed" in provider.payloads[-1]["messages"][-1]["content"]
    assert record["candidate"]["experiment_id"] == "m02-v2-development"
    for mutation in [
        lambda r: r["candidate"].update(kind="control"),
        lambda r: r["generation"].update(configuration_hash="wrong"),
        lambda r: r["generation"].update(token_reservation_upper_bound=0),
    ]:
        altered = copy.deepcopy(record)
        mutation(altered)
        with pytest.raises(ValueError):
            v2.validate(altered, f)


@pytest.mark.parametrize("error", [TimeoutError(), ProviderError("provider_http", "fixture")])
async def test_one_charged_retry_no_duplicate_tools(tmp_path, monkeypatch, error):
    record, f, provider = await run(tmp_path, monkeypatch, [error, *actions()])
    assert record["generation"]["requests"] == 5
    assert record["generation"]["retries"] == 1
    assert provider.payloads[0] == provider.payloads[1]
    assert len([e for e in record["events"] if e["kind"] == "provider_error"]) == 1
    assert len([e for e in record["events"] if e["kind"] == "tools"]) == 4
    charges = [
        json.loads(path.read_text()) for path in (tmp_path / "campaign").glob("charge-*.json")
    ]
    assert (
        sum(e["reserved_tokens"] for e in charges)
        == record["generation"]["token_reservation_upper_bound"]
    )


async def test_repeated_provider_failure_not_erased(tmp_path, monkeypatch):
    r, _, _ = await run(tmp_path, monkeypatch, [TimeoutError(), TimeoutError()])
    assert r["generation"]["generation_status"] == "provider_failure"
    assert r["generation"]["requests"] == 2 and not r["candidate"]
    assert all("usage" not in c for c in r["generation"]["provider_calls"])


async def test_truncation_preserved_and_no_automatic_candidate(tmp_path, monkeypatch):
    r, _, _ = await run(
        tmp_path,
        monkeypatch,
        [{"choices": [{"finish_reason": "length", "message": {"content": None}}]}],
    )
    assert r["generation"]["generation_status"] == "invalid_output"
    assert r["generation"]["requests"] == 1 and not r["candidate"]


def test_context_compaction_preserves_feedback_and_exact_sources():
    w = p.Workspace(task("more-bucket"), IMAGE)
    output = {
        "action": {"tool": "test"},
        "result": {
            **phase(w.files, w.spec["ordinary"], IMAGE, None),
            "stdout": "assert first\n" + "x" * 20000 + "\nFAILED last",
            "exit_code": 1,
            "policy": {"not_model_input": "large"},
        },
    }
    before = copy.deepcopy(output)
    text = p.messages(w, [output], 1, 0)[-1]["content"]
    assert "assert first" in text and "FAILED last" in text and "omitted" in text
    assert "not_model_input" not in text
    assert output == before
    assert len(p.compact(output)["result"]["stdout"].encode()) < 6300
    assert w.hashes() == task("more-bucket")["source_files"]


def test_same_turn_submit_and_invalid_source_edits_rejected(monkeypatch):
    monkeypatch.setattr(p, "execute", phase)
    w = p.Workspace(task("more-bucket"), IMAGE)
    with pytest.raises(ValueError, match="Inspect"):
        w.action(actions()[1])
    w.action(actions()[0])
    w.action(actions()[1])
    w.action(actions()[2])
    with pytest.raises(ValueError, match="feedback"):
        w.action(actions()[3])
    w.feedback_seen = True
    assert w.action(actions()[3])["status"] == "submitted"
    w = p.Workspace(task("more-bucket"), IMAGE)
    for path in [
        "../reference.json",
        "/etc/passwd",
        "backend/.env",
        "evaluation/experiments/m02-v1/freeze.json",
    ]:
        with pytest.raises(ValueError):
            w.action({"tool": "read", "path": path, "start": 1, "end": 10})
    with pytest.raises(ValueError):
        w.action(
            {"tool": "edit", "edits": [{"path": "tests/test_more.py", "old": "a", "new": "b"}]}
        )


def test_campaign_is_append_only_and_charges_unknown_usage(tmp_path):
    campaign = p.Campaign(tmp_path, create=True)
    campaign.begin("fixture")
    campaign.charge("fixture", p.Campaign.LIMIT["reserved_tokens"])
    with pytest.raises(ValueError, match="ceiling"):
        campaign.charge("fixture", 1)
    with pytest.raises(FileExistsError):
        p.Campaign(tmp_path, create=True)


async def test_passing_working_tree_not_promoted_at_request_limit(tmp_path, monkeypatch):
    monkeypatch.setitem(p.BUDGET, "requests", 3)
    r, _, _ = await run(tmp_path, monkeypatch, actions()[:3])
    assert r["generation"]["generation_status"] == "request_budget_exhausted"
    assert r["generation"]["counts"]["ordinary_runs"] == 1
    assert not r["candidate"]


async def test_reservation_ceiling_before_request(tmp_path, monkeypatch):
    monkeypatch.setitem(p.BUDGET, "token_upper_bound", 1)
    r, _, provider = await run(tmp_path, monkeypatch, [])
    assert r["generation"]["generation_status"] == "token_budget_exhausted"
    assert not provider.calls and not r["candidate"]


async def test_ordinary_failure_feedback_and_revision(tmp_path, monkeypatch):
    # Deterministic fixture only: a genuine failing transcript reaches the next model decision.
    calls = 0

    def execution(*args):
        nonlocal calls
        calls += 1
        return {
            **phase(*args),
            "exit_code": 1 if calls == 1 else 0,
            "stdout": "FAILED fixture assertion" if calls == 1 else "9 passed",
        }

    edits = candidate("more-bucket-reference")["edits"]
    revision = {
        "tool": "edit",
        "edits": [
            {
                "path": edits[0]["path"],
                "old": edits[0]["new"],
                "new": edits[0]["new"].replace(
                    "self._key = key", "self._key = key  # fixture revision"
                ),
            }
        ],
    }
    r, _, provider = await run(
        tmp_path,
        monkeypatch,
        [*actions()[:3], revision, {"tool": "test"}, {"tool": "submit"}],
        executor=execution,
    )
    assert r["generation"]["counts"]["revisions"] == 2
    assert r["generation"]["counts"]["ordinary_runs"] == 2
    assert r["candidate"]
    assert "FAILED fixture assertion" in provider.payloads[3]["messages"][-1]["content"]
    assert "9 passed" in provider.payloads[-1]["messages"][-1]["content"]


def test_invalid_python_remains_repairable_context():
    w = p.Workspace(task("more-bucket"), IMAGE)
    w.files["more_itertools/more.py"] = "def broken(:\n" + w.files["more_itertools/more.py"]
    text = p.messages(w, [], 0, 0)[1]["content"]
    assert "source_parse_error" in text
    assert digest(w.files["more_itertools/more.py"]) in text


def test_campaign_wall_and_run_reservations(tmp_path):
    c = p.Campaign(tmp_path, create=True)
    for index in range(12):
        c.begin(str(index))
    with pytest.raises(ValueError, match="ceiling"):
        c.begin("extra")


def test_failed_inspection_does_not_admit_an_edit():
    w = p.Workspace(task("more-bucket"), IMAGE)
    with pytest.raises(ValueError):
        w.action({"tool": "read", "path": "../reference.json", "start": 1, "end": 10})
    with pytest.raises(ValueError, match="Inspect"):
        w.action(actions()[1])
