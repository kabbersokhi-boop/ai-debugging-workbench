"""Validate retained trials before aggregation. No manually entered scorecards."""

import json
from collections import Counter
from pathlib import Path

from workbench.evaluator.catalog import digest, identity, public_candidate
from workbench.evaluator.experiment_catalog import ROOT, build_candidate, freeze, task
from workbench.evaluator.experiment_runner import validate_result, verifier_id
from workbench.evaluator.producer import BUDGET, HARNESS, PROMPT, Workspace, context

OUTCOMES = (
    "no_usable_candidate",
    "ordinary_failed",
    "additional_independent_failure",
    "both_passed",
    "infrastructure_or_provider_failure",
)


def assert_frozen(frozen):
    body = frozen["body"]
    if identity(body) != frozen["hash"] or body["harness"] != HARNESS or body["budget"] != BUDGET:
        raise ValueError("Frozen procedure mismatch")
    for name, wanted in body["implementation_files"].items():
        if digest((Path(__file__).parent / name).read_bytes()) != wanted:
            raise ValueError("Frozen implementation changed: " + name)
    for task_id, binding in body["tasks"].items():
        if binding != {
            "spec_hash": task(task_id)["spec_hash"],
            "verifier_hash": verifier_id(task_id),
            "context_hash": identity(context(task(task_id))),
        }:
            raise ValueError("Frozen task/verifier/context mismatch")


def read_trial(trial_id):
    frozen = freeze()
    allowed = {c["id"] for c in frozen["body"]["order"]}
    if trial_id not in allowed:
        raise ValueError("Unknown trial")
    folder = ROOT / "trials" / trial_id
    generation_path = folder / "generation.json"
    if not generation_path.exists():
        return None
    generation = json.loads(generation_path.read_text())
    events = [json.loads(p.read_text()) for p in sorted(folder.glob("event-*.json"))]
    cpath, result_path = folder / "candidate.json", folder / "evaluation.json"
    return {
        "generation": generation,
        "events": events,
        "candidate": json.loads(cpath.read_text()) if cpath.exists() else None,
        "result": json.loads(result_path.read_text())["result"] if result_path.exists() else None,
        "scoring": json.loads(result_path.read_text()) if result_path.exists() else None,
    }


def validate_trial(record, frozen):
    generation, events = record["generation"], record["events"]
    coordinates = {c["id"]: c for c in frozen["body"]["order"]}
    coordinate = coordinates.get(generation["id"])
    if (
        coordinate is None
        or generation["coordinate"] != coordinate
        or generation["freeze_hash"] != frozen["hash"]
    ):
        raise ValueError("Trial identity mismatch")
    spec = task(coordinate["task_id"])
    config = frozen["body"]["configurations"][coordinate["configuration_id"]]
    if generation["configuration_hash"] != identity(config) or generation[
        "context_hash"
    ] != identity(context(spec)):
        raise ValueError("Configuration/source access mismatch")
    head, messages = "0" * 64, []
    requests = reserved = responses = 0
    counts = {"revisions": 0, "ordinary_runs": 0, "read_search_actions": 0}
    workspace = Workspace(spec, frozen["body"]["image_id"])
    submitted = False
    expected_actions = []
    previous_kind = None
    terminal = None
    error_event = None
    response_bodies = []
    for sequence, event in enumerate(events):
        body = {k: v for k, v in event.items() if k != "hash"}
        if (
            event["trial_id"] != generation["id"]
            or event["sequence"] != sequence
            or event["previous_hash"] != head
            or identity(body) != event["hash"]
        ):
            raise ValueError("Trial event chain mismatch")
        head = event["hash"]
        kind, payload = event["kind"], event["payload"]
        allowed_previous = {
            "context": {None},
            "request": {"context", "tools"},
            "response": {"request"},
            "tools": {"response"},
            "error": {"context", "request", "response", "tools"},
            "terminal": {"context", "tools", "response", "error"},
        }
        if kind not in allowed_previous or previous_kind not in allowed_previous[kind]:
            raise ValueError("Transcript event order invalid")
        previous_kind = kind
        if kind == "context":
            if (
                sequence != 0
                or payload["coordinate"] != coordinate
                or payload["configuration"] != config
                or payload["freeze_hash"] != frozen["hash"]
            ):
                raise ValueError("Context identity mismatch")
            messages = [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(context(spec))},
            ]
            if payload["messages"] != messages or payload["source_hashes"] != spec["source_files"]:
                raise ValueError("Producer context differs from approved source")
        elif kind == "request":
            if submitted:
                raise ValueError("Provider call after submission")
            params = {
                "model": config["model"],
                "temperature": config["temperature"],
                "max_tokens": BUDGET["output_tokens_per_request"],
                "response_format": {"type": "json_object"},
            }
            size = sum(len(m["content"].encode()) for m in messages)
            requests += 1
            reserved += size + params["max_tokens"]
            if (
                payload["parameters"] != params
                or payload["messages_hash"] != identity(messages)
                or payload["request_hash"] != identity({**params, "messages": messages})
                or payload["request_index"] != requests
                or payload["input_bytes_upper_bound"] != size
                or payload["reserved_tokens"] != size + params["max_tokens"]
            ):
                raise ValueError("Request/budget evidence mismatch")
        elif kind == "response":
            response_bodies.append(payload)
            responses += 1
            if responses > requests:
                raise ValueError("Response without request")
            choices = payload.get("choices")
            choice = (
                choices[0]
                if isinstance(choices, list) and choices and isinstance(choices[0], dict)
                else {}
            )
            expected_actions = []
            if choice.get("finish_reason") == "stop" and isinstance(
                choice.get("message", {}).get("content"), str
            ):
                raw = choice["message"]["content"]
                messages.append({"role": "assistant", "content": raw})
                try:
                    expected_actions = json.loads(raw)["actions"]
                    if (
                        not isinstance(expected_actions, list)
                        or not 1 <= len(expected_actions) <= BUDGET["actions_per_response"]
                        or any(not isinstance(a, dict) for a in expected_actions)
                    ):
                        expected_actions = []
                except (ValueError, KeyError, TypeError):
                    expected_actions = []
        elif kind == "tools":
            tool_record = json.loads(payload["message"]["content"])
            outputs = tool_record["tool_results"]
            actual_actions = [o["action"] for o in outputs if "action" in o]
            if actual_actions != expected_actions:
                raise ValueError("Tools differ from actual model decisions")
            workspace.feedback_seen = True
            for output in outputs:
                if "action" not in output:
                    if expected_actions:
                        raise ValueError("Missing model tool action")
                    continue
                action = output["action"]
                hashes = workspace.hashes()
                if output["before"] != hashes:
                    raise ValueError("Concurrent or mixed workspace detected")
                if "execution_error" in output:
                    if action != {"tool": "test"}:
                        raise ValueError("Unexpected tool infrastructure error")
                    workspace.counts["ordinary_runs"] += 1
                    if output["after"] != hashes:
                        raise ValueError("Infrastructure failure changed source")
                    continue
                if output.get("error") in (
                    "Wall budget exhausted before action",
                    "Infrastructure failure before action",
                ):
                    if output["after"] != hashes:
                        raise ValueError("Wall timeout changed source")
                    continue
                if (
                    action.get("tool") == "test"
                    and set(action) == {"tool"}
                    and not workspace.submitted
                    and (not workspace.last_test_failed or workspace.feedback_seen)
                    and workspace.counts["ordinary_runs"] < BUDGET["ordinary_runs"]
                ):
                    phase = output["result"]
                    workspace.counts["ordinary_runs"] += 1
                    if (
                        phase["command"] != spec["ordinary"]
                        or phase["image_id"] != frozen["body"]["image_id"]
                        or phase["executed_file_hashes"] != hashes
                        or not phase.get("container_id")
                    ):
                        raise ValueError("Ordinary tool execution binding mismatch")
                    workspace.tested_hash = identity(hashes)
                    workspace.last_test_failed = phase.get("exit_code") != 0
                    workspace.feedback_seen = not workspace.last_test_failed
                else:
                    try:
                        replayed = workspace.action(action)
                    except (ValueError, TypeError, KeyError) as exc:
                        if output.get("error") != str(exc):
                            raise ValueError("Stored tool error differs from replay") from None
                    else:
                        if output.get("result") != replayed or "error" in output:
                            raise ValueError("Stored tool response differs from replay")
                if output["after"] != workspace.hashes():
                    raise ValueError("Tool result source mismatch")
            if payload["source_hashes"] != workspace.hashes():
                raise ValueError("Tool workspace mismatch")
            submitted = workspace.submitted
            messages.append(payload["message"])
        elif kind == "error":
            error_event = payload
        elif kind == "terminal":
            if sequence != len(events) - 1:
                raise ValueError("Events after terminal state")
            terminal = payload
    counts = workspace.counts
    edits = workspace.edits
    if (
        generation["events_count"] != len(events)
        or generation["events_head"] != head
        or generation["requests"] != requests
        or generation["token_reservation_upper_bound"] != reserved
        or generation["counts"] != counts
        or requests > BUDGET["requests"]
        or reserved > BUDGET["token_upper_bound"]
        or any(counts[k] > BUDGET[k] for k in counts)
    ):
        raise ValueError("Trial accounting mismatch")
    if len(generation["provider_calls"]) != requests or any(
        c["attempt"] != 1 for c in generation["provider_calls"]
    ):
        raise ValueError("Provider retry/accounting mismatch")
    if terminal is None or terminal != {
        "status": generation["generation_status"],
        "error": generation["error"],
        "requests": requests,
        "reserved_tokens": reserved,
        "source_hashes": workspace.hashes(),
        "counts": counts,
        "elapsed_ms": terminal["elapsed_ms"],
    }:
        raise ValueError("Terminal evidence mismatch")
    status = generation["generation_status"]
    if error_event != generation["error"]:
        raise ValueError("Terminal error mismatch")
    if error_event:
        expected_status = (
            "provider_failure"
            if error_event["type"] in ("ProviderError", "TimeoutError")
            else "infrastructure_failure"
        )
    elif submitted:
        expected_status = "submitted"
    elif status == "generation_timeout" and terminal["elapsed_ms"] >= BUDGET["wall_seconds"] * 1000:
        expected_status = status
    elif (
        previous_kind == "terminal"
        and response_bodies
        and (
            response_bodies[-1]["choices"][0].get("finish_reason") != "stop"
            or not isinstance(
                response_bodies[-1]["choices"][0].get("message", {}).get("content"), str
            )
        )
    ):
        expected_status = "invalid_output"
    elif requests == BUDGET["requests"]:
        expected_status = "request_budget_exhausted"
    elif (
        reserved
        + sum(len(m["content"].encode()) for m in messages)
        + BUDGET["output_tokens_per_request"]
        > BUDGET["token_upper_bound"]
    ):
        expected_status = "token_budget_exhausted"
    else:
        raise ValueError("Unexplained terminal outcome")
    if status != expected_status or responses != requests - int(
        bool(error_event) and responses < requests
    ):
        raise ValueError("Terminal/provider completion mismatch")
    for index, call in enumerate(generation["provider_calls"]):
        if call.get("model") != config["model"]:
            raise ValueError("Provider requested model mismatch")
        if index < len(response_bodies):
            response = response_bodies[index]
            if call.get("status") != 200:
                raise ValueError("Response without successful provider call")
            usage = response.get("usage")
            if isinstance(usage, dict):
                wanted_usage = {
                    k: v
                    for k, v in usage.items()
                    if k in ("prompt_tokens", "completion_tokens", "total_tokens")
                    and isinstance(v, int)
                }
                if call.get("usage") != wanted_usage:
                    raise ValueError("Provider usage differs from response")
    c, result = record.get("candidate"), record.get("result")
    if c:
        if (
            not submitted
            or generation["generation_status"] != "submitted"
            or c["kind"] != "agent"
            or c["id"] != generation["id"]
            or c["task_id"] != spec["id"]
            or c["spec_hash"] != spec["spec_hash"]
            or c["producer"] != config["model"]
            or c["label"] != config["label"] + " · trial " + str(coordinate["trial"])
            or c["experiment_id"] != frozen["body"]["id"]
            or c["trial_id"] != generation["id"]
            or c["generation"] != "trials/" + generation["id"]
            or c["edits"] != edits
            or c["freeze_hash"] != frozen["hash"]
            or c["configuration_hash"] != identity(config)
            or c["events_head"] != head
            or generation["candidate_id"] != c["id"]
        ):
            raise ValueError("Final candidate provenance mismatch; controls are ineligible")
        full = build_candidate(spec, c)
        if generation["candidate_hash"] != full["candidate_hash"]:
            raise ValueError("Final candidate identity mismatch")
        if result:
            scoring = record.get("scoring")
            provenance = trial_binding(record, frozen)
            if (
                not scoring
                or scoring["trial_binding"] != provenance
                or scoring["trial_binding_hash"] != identity(provenance)
                or scoring["result_hash"] != identity(result)
                or result.get("trial_binding_hash") != identity(provenance)
            ):
                raise ValueError("Scoring belongs to a different trial")
            validate_result(spec, full, result, frozen["body"]["image_id"])
    elif submitted or generation["candidate_id"] is not None or result:
        raise ValueError("Missing final candidate")
    return record


def trial_binding(record, frozen):
    generation = record["generation"]
    return {
        "trial_id": generation["id"],
        "freeze_hash": frozen["hash"],
        "configuration_hash": generation["configuration_hash"],
        "events_head": generation["events_head"],
        "candidate_hash": record["candidate"]["candidate_hash"],
    }


def outcome(record):
    generation, result = record["generation"], record.get("result")
    if generation["generation_status"] in (
        "provider_failure",
        "infrastructure_failure",
        "generation_timeout",
    ):
        return "infrastructure_or_provider_failure"
    if not record.get("candidate"):
        return "no_usable_candidate"
    if result is None:
        return "awaiting_evaluation"
    if result["status"] not in ("passed", "failed", "invalid_candidate"):
        return "infrastructure_or_provider_failure"
    if result["ordinary"].get("outcome") == "failed":
        return "ordinary_failed"
    if result["independent"].get("outcome") != "passed":
        return "additional_independent_failure"
    return "both_passed"


def comparison(records, frozen, require_complete=False):
    seen, rows = set(), []
    for record in records:
        validate_trial(record, frozen)
        key = record["generation"]["id"]
        if key in seen:
            raise ValueError("Duplicate trial")
        seen.add(key)
        rows.append(record)
    complete = seen == {c["id"] for c in frozen["body"]["order"]} and all(
        outcome(r) != "awaiting_evaluation" for r in rows
    )
    if require_complete and not complete:
        raise ValueError("Final comparison requires the entire scored trial matrix")
    containers = [
        r["result"][p]["container_id"]
        for r in rows
        if r.get("result")
        for p in ("ordinary", "independent")
        if r["result"].get(p)
    ]
    if len(containers) != len(set(containers)):
        raise ValueError("Execution evidence reused across trials")
    groups = []
    for config_id, config in frozen["body"]["configurations"].items():
        values = [r for r in rows if r["generation"]["coordinate"]["configuration_id"] == config_id]
        counts = Counter(outcome(r) for r in values)
        reported_usage = [
            e["payload"].get("usage")
            for r in values
            for e in r["events"]
            if e["kind"] == "response"
        ]
        missing = sum(
            not isinstance(u, dict) or not isinstance(u.get("total_tokens"), int)
            for u in reported_usage
        )
        missing += sum(r["generation"]["requests"] for r in values) - len(reported_usage)
        completed = (
            counts["ordinary_failed"]
            + counts["additional_independent_failure"]
            + counts["both_passed"]
        )
        groups.append(
            {
                "id": config_id,
                "configuration": config,
                "attempted": len(values),
                "scheduled": sum(
                    c["configuration_id"] == config_id for c in frozen["body"]["order"]
                ),
                "completed": completed,
                "outcomes": {k: counts[k] for k in OUTCOMES},
                "awaiting_evaluation": counts["awaiting_evaluation"],
                "incremental_numerator": counts["additional_independent_failure"],
                "incremental_denominator": counts["additional_independent_failure"]
                + counts["both_passed"],
                "requests": sum(r["generation"]["requests"] for r in values),
                "reported_total_tokens": sum(
                    u.get("total_tokens", 0) for u in reported_usage if isinstance(u, dict)
                ),
                "usage_missing_requests": missing,
                "monetary_cost": None,
                "generation_wall_ms": sum(r["generation"]["generation_wall_ms"] for r in values),
                "ordinary_tool_ms": sum(r["generation"]["ordinary_tool_ms"] for r in values),
                "evaluation_ms": sum(
                    sum(
                        (r.get("result", {}).get(p) or {}).get("duration_ms", 0)
                        for p in ("ordinary", "independent")
                    )
                    for r in values
                    if r.get("result")
                ),
            }
        )
    trials = [
        {
            "id": r["generation"]["id"],
            "coordinate": r["generation"]["coordinate"],
            "outcome": outcome(r),
            "generation_status": r["generation"]["generation_status"],
            "candidate_hash": (r.get("candidate") or {}).get("candidate_hash"),
            "evaluation_id": r.get("evaluation_id"),
        }
        for r in rows
    ]
    return {
        "experiment_id": frozen["body"]["id"],
        "freeze_hash": frozen["hash"],
        "complete": complete,
        "attempted": len(rows),
        "scheduled": len(frozen["body"]["order"]),
        "groups": groups,
        "trials": trials,
        "controls_in_denominator": False,
        "generation_mode": "controlled generation plus common verification",
        "historical_m1": (
            "M1 single-turn evidence is separate. M1 found no genuine "
            "ordinary-pass/independent-fail patch."
        ),
        "limitations": frozen["body"]["limitations"],
    }


def trial_public(record):
    value = dict(record)
    if value.get("candidate"):
        value["candidate"] = public_candidate(
            build_candidate(task(value["candidate"]["task_id"]), value["candidate"])
        )
    return value
