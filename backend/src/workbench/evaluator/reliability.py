"""One bounded M2 reliability pass: versioned freeze, replay and fixed local CLI."""

import argparse
import asyncio
import json
import random
from pathlib import Path

from workbench.evaluator import experiment as v1
from workbench.evaluator import reliability_producer as producer
from workbench.evaluator.catalog import digest, identity
from workbench.evaluator.experiment_catalog import ROOT as V1_ROOT
from workbench.evaluator.experiment_catalog import build_candidate, exclusive_json, task
from workbench.evaluator.experiment_catalog import freeze as old_freeze
from workbench.evaluator.experiment_runner import evaluate, validate_result, verifier_id

ROOT = V1_ROOT.parent / "m02-v2"
DEV = ROOT / "development"
CAMPAIGN = ROOT / "accounting"
TASKS = ("more-seekable", "boltons-indexedset")
CODE = ("reliability.py", "reliability_producer.py", "reliability_store.py")


def configurations():
    return {
        k: {
            **v,
            "label": v["label"].replace("v2", "v3"),
            "harness": producer.HARNESS,
            "budget": producer.BUDGET,
            "prompt_hash": digest(producer.PROMPT),
            "harness_hash": digest(Path(producer.__file__).read_bytes()),
            "automatic_retries": 1,
            "parameters": {
                "temperature": 1,
                "top_p": 0.95,
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
                "chat_template_kwargs": {"enable_thinking": False},
            },
            "reasoning_policy": "Explicit supported reasoning-off; no partial/truncated actions",
            "context_policy": (
                "Current source excerpts; all edits/errors/test feedback; last two "
                "reads; logs head/tail 6000 bytes each"
            ),
            "retry_policy": (
                "At most one transient HTTP/timeout retry per trial, identical "
                "payload, charged before sending; no tool side effects on errors"
            ),
        }
        for k, v in old_freeze()["body"]["configurations"].items()
    }


def definition(development=False):
    ids = ("more-bucket", "boltons-addlist") if development else TASKS
    experiment_id = "m02-v2-development" if development else "m02-v2"
    order = []
    pairs = [(t, r) for r in range(1, 3) for t in ids]
    if development:
        pairs = [(ids[0], 1), (ids[1], 2)]
    else:
        random.Random(20261017).shuffle(pairs)
    for index, (task_id, repeat) in enumerate(pairs):
        configs = ["nemotron3", "nemotron35"] if index % 2 == 0 else ["nemotron35", "nemotron3"]
        for config in configs:
            order.append(
                {
                    "id": f"{experiment_id}-{task_id}-{config}-r{repeat:02d}",
                    "task_id": task_id,
                    "configuration_id": config,
                    "trial": repeat,
                    "order": len(order),
                }
            )
    body = {
        "id": experiment_id,
        "frozen_at": producer.historical.now(),
        "parent_v1_hash": old_freeze()["hash"],
        "harness": producer.HARNESS,
        "prompt_hash": digest(producer.PROMPT),
        "budget": producer.BUDGET,
        "configurations": configurations(),
        "order": order,
        "order_seed": 20261017,
        "image_id": old_freeze()["body"]["image_id"],
        "implementation_files": {n: digest((Path(__file__).parent / n).read_bytes()) for n in CODE},
        "tasks": {
            t: {"spec_hash": task(t)["spec_hash"], "verifier_hash": verifier_id(t)} for t in ids
        },
        "campaign_ceiling_including_development": producer.Campaign.LIMIT,
        "scoring_rule": (
            "All generation terminates before fresh ordinary and independent "
            "scoring. Never feed scoring back."
        ),
        "admission": (
            "Explicit model submit after inspected source, valid edit and "
            "feedback from ordinary test of final source; ordinary pass not "
            "required."
        ),
        "limitations": [
            "Small historical tasks; training contamination unknown.",
            "Procedures differ from v1; no pooled or causal reliability ranking.",
            "Reported usage excludes unknown failed-request usage; cost unknown.",
            "In-process Python observations are not a complete malicious-candidate boundary.",
        ],
    }
    return {"body": body, "hash": identity(body)}


def load_freeze(development=False):
    return json.loads(((DEV if development else ROOT) / "freeze.json").read_text())


def assert_frozen(frozen):
    v1.assert_frozen(old_freeze())
    b = frozen["body"]
    if (
        identity(b) != frozen["hash"]
        or b["budget"] != producer.BUDGET
        or b["harness"] != producer.HARNESS
    ):
        raise ValueError("Reliability freeze mismatch")
    for name, wanted in b["implementation_files"].items():
        if digest((Path(__file__).parent / name).read_bytes()) != wanted:
            raise ValueError("Frozen reliability implementation changed: " + name)
    for t, binding in b["tasks"].items():
        if binding != {"spec_hash": task(t)["spec_hash"], "verifier_hash": verifier_id(t)}:
            raise ValueError("Frozen task/verifier mismatch")
    for config in b["configurations"].values():
        if (
            config["budget"] != producer.BUDGET
            or config["parameters"] != next(iter(configurations().values()))["parameters"]
        ):
            raise ValueError("Unfair provider procedure")


def read_trial(coordinate, development=False):
    folder = (DEV if development else ROOT) / "trials" / coordinate["id"]

    def read(name):
        p = folder / (name + ".json")
        return json.loads(p.read_text()) if p.exists() else None

    scoring = read("evaluation")
    return {
        "generation": read("generation"),
        "candidate": read("candidate"),
        "events": [json.loads(p.read_text()) for p in sorted(folder.glob("event-*.json"))],
        "scoring": scoring,
        "result": scoring["result"] if scoring else None,
    }


def validate(record, frozen):
    g, events = record["generation"], record["events"]
    if g is None:
        raise ValueError("Incomplete raw trial; never restart or replace")
    coord = next((c for c in frozen["body"]["order"] if c["id"] == g["id"]), None)
    if coord is None or coord != g["coordinate"] or g["freeze_hash"] != frozen["hash"]:
        raise ValueError("Trial coordinate/freeze mismatch")
    config = frozen["body"]["configurations"][coord["configuration_id"]]
    if g["configuration_hash"] != identity(config):
        raise ValueError("Configuration mismatch")
    spec = task(coord["task_id"])
    workspace = producer.Workspace(spec, frozen["body"]["image_id"])
    head, history = "0" * 64, []
    requests = reserved = retries = 0
    pending = action = previous_payload = None
    stage, error = "context", None
    responses = []
    terminal = None
    for sequence, event in enumerate(events):
        if (
            event["trial_id"] != g["id"]
            or event["sequence"] != sequence
            or event["previous_hash"] != head
            or event["hash"] != identity({k: v for k, v in event.items() if k != "hash"})
        ):
            raise ValueError("Event chain mismatch")
        head = event["hash"]
        kind, p = event["kind"], event["payload"]
        if kind == "context" and sequence == 0:
            if p != {
                "coordinate": coord,
                "freeze_hash": frozen["hash"],
                "configuration": config,
                "source_hashes": workspace.hashes(),
            }:
                raise ValueError("Initial context mismatch")
            stage = "request"
        elif kind == "request" and stage == "request" and not workspace.submitted:
            wanted = (
                previous_payload
                if pending
                else {
                    **config["parameters"],
                    "model": config["model"],
                    "messages": producer.messages(workspace, history, requests, reserved),
                }
            )
            assert isinstance(wanted, dict)
            amount = (
                sum(len(m["content"].encode()) for m in wanted["messages"]) + wanted["max_tokens"]
            )
            if p != {
                "payload": wanted,
                "request_hash": identity(wanted),
                "request_index": requests + 1,
                "retry_of": pending,
                "reserved_tokens": amount,
            }:
                raise ValueError("Request/context/reservation mismatch")
            if amount - wanted["max_tokens"] > producer.BUDGET["input_bytes_per_request"]:
                raise ValueError("Per-request context ceiling exceeded")
            requests += 1
            reserved += amount
            previous_payload, stage = wanted, "response"
        elif kind == "provider_error" and stage == "response":
            assert isinstance(p, dict)
            if p["request_index"] != requests:
                raise ValueError("Provider error identity mismatch")
            error = {k: v for k, v in p.items() if k != "retry_planned"}
            if p["retry_planned"]:
                transient = (
                    p["type"] == "TimeoutError"
                    or p["code"] == "provider_unavailable"
                    or p["call"].get("status") in (429, 500, 502, 503, 504)
                )
                if not transient or retries or requests >= producer.BUDGET["requests"]:
                    raise ValueError("Invalid retry policy")
                retries += 1
                pending, error, stage = requests, None, "request"
            else:
                stage = "terminal"
        elif kind == "response" and stage == "response":
            responses.append((requests, p))
            pending = None
            try:
                action = producer.decision(p)
                stage = "tools"
            except ValueError:
                stage = "invalid_decision"
        elif kind == "invalid_decision" and stage == "invalid_decision":
            try:
                producer.decision(responses[-1][1])
            except ValueError as exc:
                if p != {"error": str(exc)}:
                    raise ValueError("Invalid-output explanation mismatch") from None
            stage = "terminal"
        elif kind == "tools" and stage == "tools":
            if action is None or p.get("action") != action or p["before"] != workspace.hashes():
                raise ValueError("Model action/source mismatch")
            workspace.feedback_seen = True
            if (
                action == {"tool": "test"}
                and "result" not in p
                and workspace.counts["ordinary_runs"] < producer.BUDGET["ordinary_runs"]
                and not workspace.submitted
            ):
                raise ValueError("Missing ordinary tool evidence")
            try:
                replayed = workspace.action(
                    action, p.get("result") if action == {"tool": "test"} else None
                )
            except (ValueError, TypeError, KeyError) as exc:
                if p.get("error") != str(exc):
                    raise ValueError("Tool error differs from replay") from None
            else:
                if p.get("result") != replayed or "error" in p:
                    raise ValueError("Tool result differs from replay")
            if p["after"] != workspace.hashes():
                raise ValueError("Tool source mismatch")
            history.append(p)
            stage = "request"
        elif kind == "deadline" and stage == "tools" and action == {"tool": "test"}:
            if p != {"reason": "Insufficient remaining wall for fixed ordinary tool"}:
                raise ValueError("Unknown deadline admission")
            stage = "terminal"
        elif kind == "infrastructure_error":
            error, stage = p, "terminal"
        elif (
            kind == "terminal" and sequence == len(events) - 1 and stage in ("request", "terminal")
        ):
            terminal = p
        else:
            raise ValueError("Invalid event order")
    if (
        terminal is None
        or g["events_head"] != head
        or g["events_count"] != len(events)
        or g["requests"] != requests
        or g["token_reservation_upper_bound"] != reserved
        or g["ordinary_tool_ms"] != workspace.test_ms
        or g["counts"] != workspace.counts
        or g["retries"] != retries
        or requests > producer.BUDGET["requests"]
        or reserved > producer.BUDGET["token_upper_bound"]
        or terminal
        != {
            "status": g["generation_status"],
            "error": g["error"],
            "requests": requests,
            "reserved_tokens": reserved,
            "retries": retries,
            "counts": workspace.counts,
            "source_hashes": workspace.hashes(),
            "elapsed_ms": g["generation_wall_ms"],
        }
        or error != g["error"]
        or len(g["provider_calls"]) != requests
    ):
        raise ValueError("Terminal accounting mismatch")
    if g["context_hash"] != identity(producer.historical.context(spec)):
        raise ValueError("Source context identity mismatch")
    for index, call in enumerate(g["provider_calls"], 1):
        if call.get("model") != config["model"] or call.get("attempt") != 1:
            raise ValueError("Provider attempt identity mismatch")
        failure = next(
            (
                e["payload"]
                for e in events
                if e["kind"] == "provider_error" and e["payload"]["request_index"] == index
            ),
            None,
        )
        if failure and failure["call"] != call:
            raise ValueError("Provider failure metadata mismatch")
    assert terminal is not None
    status = g["generation_status"]
    if error:
        expected_status = (
            "provider_failure" if "request_index" in error else "infrastructure_failure"
        )
    elif workspace.submitted:
        expected_status = "submitted"
    elif any(e["kind"] == "invalid_decision" for e in events[-2:]):
        expected_status = "invalid_output"
    elif terminal["elapsed_ms"] >= producer.BUDGET["wall_seconds"] * 1000 or any(
        e["kind"] == "deadline" for e in events[-2:]
    ):
        expected_status = "generation_timeout"
    elif requests == producer.BUDGET["requests"]:
        expected_status = "request_budget_exhausted"
    else:
        next_messages = producer.messages(workspace, history, requests, reserved)
        size = sum(len(m["content"].encode()) for m in next_messages)
        if (
            size > producer.BUDGET["input_bytes_per_request"]
            or reserved + size + producer.BUDGET["output_tokens_per_request"]
            > producer.BUDGET["token_upper_bound"]
        ):
            expected_status = "token_budget_exhausted"
        elif status == "campaign_budget_exhausted":
            expected_status = status
        else:
            raise ValueError("Unexplained terminal outcome")
    if status != expected_status:
        raise ValueError("Terminal outcome mismatch")
    for index, response in responses:
        call = g["provider_calls"][index - 1]
        if call.get("status") != 200 or call["model"] != config["model"]:
            raise ValueError("Provider call identity mismatch")
        usage = response.get("usage")
        if isinstance(usage, dict) and call.get("usage") != {
            k: v
            for k, v in usage.items()
            if k in ("prompt_tokens", "completion_tokens", "total_tokens") and isinstance(v, int)
        }:
            raise ValueError("Provider usage mismatch")
    candidate = record.get("candidate")
    if bool(candidate) != workspace.submitted or workspace.submitted != (
        g["generation_status"] == "submitted"
    ):
        raise ValueError("Incomplete candidate promotion")
    if candidate:
        expected = {
            "id": g["id"],
            "task_id": spec["id"],
            "spec_hash": spec["spec_hash"],
            "kind": "agent",
            "label": config["label"] + " · trial " + str(coord["trial"]),
            "producer": config["model"],
            "experiment_id": frozen["body"]["id"],
            "trial_id": g["id"],
            "edits": workspace.edits,
            "freeze_hash": frozen["hash"],
            "events_head": head,
            "configuration_hash": identity(config),
            "provenance": "Genuine bounded source/tool producer; no independent feedback.",
        }
        expected["candidate_hash"] = build_candidate(spec, expected)["candidate_hash"]
        if (
            candidate != expected
            or g["candidate_id"] != g["id"]
            or g["candidate_hash"] != expected["candidate_hash"]
        ):
            raise ValueError("Final candidate identity mismatch")
        if record.get("result"):
            binding = v1.trial_binding(record, frozen)
            scoring, result = record["scoring"], record["result"]
            if scoring != {
                "trial_binding": binding,
                "trial_binding_hash": identity(binding),
                "result_hash": identity(result),
                "result": result,
            } or result.get("trial_binding_hash") != identity(binding):
                raise ValueError("Score trial binding mismatch")
            validate_result(
                spec, build_candidate(spec, candidate), result, frozen["body"]["image_id"]
            )
    elif record.get("result") or g["candidate_id"] is not None:
        raise ValueError("Score without candidate")
    return record


def ready(records):
    return all(
        any(
            r["generation"]["coordinate"]["configuration_id"] == cid
            and r.get("candidate")
            and any(
                e["kind"] == "tools"
                and e["payload"].get("action") == {"tool": "test"}
                and e["payload"].get("result", {}).get("exit_code") == 0
                for e in r["events"]
            )
            for r in records
        )
        for cid in configurations()
    )


def records(development=False):
    frozen = load_freeze(development)
    return [validate(read_trial(c, development), frozen) for c in frozen["body"]["order"]]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "prepare",
            "preflight",
            "freeze",
            "generate",
            "score",
            "summary",
            "import",
            "reproduce",
        ),
    )
    parser.add_argument("candidate_id", nargs="?")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        producer.Campaign(CAMPAIGN, create=True)
        exclusive_json(DEV / "freeze.json", definition(True))
        return
    if args.command == "freeze":
        dev = records(True)
        if not ready(dev):
            raise ValueError("Preflight readiness gate failed; no formal comparison authorized")
        f = definition()
        f["body"]["development_evidence"] = {
            r["generation"]["id"]: r["generation"]["events_head"] for r in dev
        }
        f["body"]["preflight_returned_models"] = {
            cid: sorted(
                {
                    e["payload"].get("model", "unknown")
                    for r in dev
                    if r["generation"]["coordinate"]["configuration_id"] == cid
                    for e in r["events"]
                    if e["kind"] == "response"
                }
            )
            for cid in configurations()
        }
        f["body"]["campaign_charges_before_formal"] = {
            p.name: digest(p.read_bytes()) for p in sorted(CAMPAIGN.glob("charge-*.json"))
        }
        f["hash"] = identity(f["body"])
        exclusive_json(ROOT / "freeze.json", f)
        return
    development = args.command == "preflight"
    f = load_freeze(development)
    assert_frozen(f)
    folder = DEV if development else ROOT
    if args.command in ("preflight", "generate"):
        if not args.live:
            parser.error("Explicit --live required for genuine provider calls")
        if not development and not ready(records(True)):
            raise ValueError("Preflight readiness gate failed")
        exclusive_json(folder / "generation-claim.json", {"freeze_hash": f["hash"]})
        for c in f["body"]["order"]:
            g = await producer.generate(
                task(c["task_id"]),
                f["body"]["configurations"][c["configuration_id"]],
                c,
                f,
                folder / "trials" / c["id"],
                producer.Campaign(CAMPAIGN),
            )
            validate(read_trial(c, development), f)
            print(c["id"], g["generation_status"], flush=True)
        return
    if args.command == "reproduce":
        values = [
            r for r in records() if r.get("candidate") and r["candidate"]["id"] == args.candidate_id
        ]
        if len(values) != 1:
            raise ValueError("Unknown approved candidate")
        c = values[0]["candidate"]
        result = await asyncio.to_thread(
            evaluate, task(c["task_id"]), build_candidate(task(c["task_id"]), c)
        )
        text = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.write_text(text)
        print(text)
        raise SystemExit(0 if result["status"] == "passed" else 1)
    values = records()
    if args.command == "score":
        for r in values:
            if not r.get("candidate") or r.get("result"):
                continue
            c = r["candidate"]
            path = ROOT / "trials" / c["id"]
            binding = v1.trial_binding(r, f)
            if (path / "scoring-claim.json").exists():
                if json.loads((path / "scoring-claim.json").read_text()) != binding:
                    raise ValueError("Conflicting scoring claim")
                result = {
                    "candidate_hash": c["candidate_hash"],
                    "status": "infrastructure_error",
                    "reason": "InterruptedScoring: no re-execution",
                }
            else:
                exclusive_json(path / "scoring-claim.json", binding)
                try:
                    result = await asyncio.to_thread(
                        evaluate, task(c["task_id"]), build_candidate(task(c["task_id"]), c)
                    )
                except Exception as exc:
                    result = {
                        "candidate_hash": c["candidate_hash"],
                        "status": "infrastructure_error",
                        "reason": type(exc).__name__,
                    }
            result["trial_binding_hash"] = identity(binding)
            exclusive_json(
                path / "evaluation.json",
                {
                    "trial_binding": binding,
                    "trial_binding_hash": identity(binding),
                    "result_hash": identity(result),
                    "result": result,
                },
            )
            validate(read_trial(r["generation"]["coordinate"]), f)
            print(c["id"], result["status"], flush=True)
    if args.command in ("summary", "import"):
        from workbench.evaluator import reliability_store

        if args.command == "import":
            for r in values:
                await reliability_store.insert(r, f)
        text = json.dumps(reliability_store.comparison(values, f), indent=2) + "\n"
        if args.output:
            args.output.write_text(text)
        print(text)


if __name__ == "__main__":
    asyncio.run(main())
