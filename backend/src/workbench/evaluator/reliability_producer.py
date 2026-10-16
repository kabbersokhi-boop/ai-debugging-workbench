"""Versioned producer correction. Historical producer.py remains immutable."""

import asyncio
import json
import threading
import time

from workbench.config import ProviderSettings
from workbench.evaluator import producer as historical
from workbench.evaluator.catalog import digest, identity
from workbench.evaluator.experiment_catalog import build_candidate, exclusive_json
from workbench.evaluator.runner import execute
from workbench.rag.provider import NvidiaProvider, sanitize_model_text

HARNESS = "json-source-tools-v3"
BUDGET = {
    **historical.BUDGET,
    "requests": 12,
    "output_tokens_per_request": 4096,
    "token_upper_bound": 360000,
    "wall_seconds": 720,
    "provider_timeout_seconds": 90,
    "actions_per_response": 1,
    "automatic_retries": 1,
    "input_bytes_per_request": 48000,
}
PROMPT = """Repair the approved upstream Python source using the tools below. No shell or retrieval.
Return ONE JSON tool object per response, with a brief optional "decision" explanation.
{"tool":"read","path":"approved path","start":1,"end":100} (inclusive, at most 120 lines)
{"tool":"search","query":"literal text"} (approved source/tests only, 20 hits)
{"tool":"edit","edits":[{"path":"production path","old":"exact unique source","new":"replacement"}]}
{"tool":"test"} (fixed upstream ordinary tests in a fresh restricted container)
{"tool":"submit"} (explicit final submission, after an edit and ordinary test of the latest source).
A legacy {"actions":[ONE tool object]} wrapper is also accepted. No markdown fences.
Inspect source before editing. Tests may be read and executed, never edited. Source excerpts and
hashes reflect the CURRENT working tree. Previous exact actions and full logs are retained
externally;
your bounded state contains recent reads, test feedback, edit/error history and current identities.
Read again if you need omitted source. Correct ordinary failures when justified and within budget.
You must receive the test feedback on a later turn before submitting. You may explicitly submit a
candidate whose ordinary tests fail; never claim that it passed. Passing tests is not proof of
correctness.
No reference fix, independent checks or evaluation feedback is available. Preserve documented
behavior.
Use the last two requests for testing/submission, not further exploration. No automatic submission.
"""


def decision(body):
    """Never execute truncated or content-null responses; normalize only declared syntax."""
    try:
        choice = body["choices"][0]
        raw = choice["message"]["content"]
        if choice.get("finish_reason") != "stop" or not isinstance(raw, str) or not raw.strip():
            raise ValueError("Truncated, empty or content-null response")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON tool object")
        if "actions" in value:
            actions = value["actions"]
            if not isinstance(actions, list) or len(actions) != 1:
                raise ValueError("Exactly one tool action per response")
            value = actions[0]
        else:
            value = {k: v for k, v in value.items() if k != "decision"}
        if not isinstance(value, dict):
            raise ValueError("Expected a tool object")
        return value
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid JSON tool protocol") from error


class Workspace(historical.Workspace):
    def __init__(self, spec, image_id):
        super().__init__(spec, image_id)
        self.inspected = False

    def action(self, action, phase=None):
        if action.get("tool") == "edit" and not self.inspected:
            raise ValueError("Inspect approved source with read/search before editing")
        if action.get("tool") == "submit" and not self.feedback_seen:
            raise ValueError(
                "Receive ordinary-test feedback on the next decision before submitting"
            )
        if action == {"tool": "test"}:
            if self.submitted or self.counts["ordinary_runs"] >= BUDGET["ordinary_runs"]:
                raise ValueError("Ordinary-test budget exhausted or already submitted")
            self.counts["ordinary_runs"] += 1
            result = (
                phase
                if phase is not None
                else execute(self.files, self.spec["ordinary"], self.image_id, threading.Event())
            )
            if (
                result.get("command") != self.spec["ordinary"]
                or result.get("image_id") != self.image_id
                or result.get("executed_file_hashes") != self.hashes()
                or not result.get("container_id")
            ):
                raise ValueError("Ordinary execution identity mismatch")
            self.tested_hash = identity(self.hashes())
            self.last_test_failed = result.get("exit_code") != 0
            self.feedback_seen = False
            self.test_ms += result["duration_ms"]
            return result
        result = super().action(action)
        if action.get("tool") in ("read", "search"):
            self.inspected = True
        return result


def bounded_text(value, limit):
    raw = value.encode()
    if len(raw) <= limit:
        return value
    # Keep both assertion setup and final failure summary; omission is explicit and hashed.
    half = limit // 2
    return (
        raw[:half].decode(errors="ignore")
        + f"\n[omitted {len(raw) - limit} bytes; full log sha256={digest(value)}]\n"
        + raw[-half:].decode(errors="ignore")
    )


def compact(output):
    result = output.get("result")
    if output.get("action", {}).get("tool") == "test" and isinstance(result, dict):
        return {
            "action": output["action"],
            "result": {
                k: bounded_text(v, 6000) if k in ("stdout", "stderr") else v
                for k, v in result.items()
                if k
                in (
                    "status",
                    "exit_code",
                    "stdout",
                    "stderr",
                    "command",
                    "duration_ms",
                    "container_id",
                    "image_id",
                    "executed_file_hashes",
                )
            },
        }
    return output


def messages(workspace, history, requests, reserved):
    spec = {**workspace.spec, "files": workspace.files}
    try:
        initial = historical.context(spec)
    except SyntaxError as exc:
        initial = historical.context(workspace.spec)
        initial["source_parse_error"] = str(exc)
        for excerpt in initial["source_excerpts"]:
            excerpt["content"] = "".join(
                workspace.files[excerpt["path"]].splitlines(True)[
                    excerpt["start"] - 1 : excerpt["end"]
                ]
            )
        initial["files"] = {
            p: {"lines": len(v.splitlines()), "sha256": digest(v)}
            for p, v in workspace.files.items()
        }
    initial["budget"] = BUDGET
    # Exact edits, errors and all bounded test feedback persist. Only old successful reads expire.
    important = [
        compact(o)
        for o in history
        if o.get("error") or o.get("action", {}).get("tool") in ("edit", "test", "submit")
    ]
    reads = [o for o in history if o.get("action", {}).get("tool") in ("read", "search")][-2:]
    state = {
        "source_hashes": workspace.hashes(),
        "counts": workspace.counts,
        "tested_source_hash": workspace.tested_hash,
        "feedback": important + reads,
        "requests_remaining": BUDGET["requests"] - requests,
        "reservation_remaining": BUDGET["token_upper_bound"] - reserved,
        "instruction": "Submit explicitly now if your final edited source has been tested."
        if workspace.tested_hash == identity(workspace.hashes())
        else "Inspect/edit, run ordinary tests, receive feedback, then explicitly submit.",
    }
    return [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": json.dumps(initial)},
        {"role": "user", "content": json.dumps(state)},
    ]


class Campaign:
    """One cross-development/formal durable ledger. Exclusive writer for the whole pass."""

    LIMIT = {"runs": 12, "requests": 144, "reserved_tokens": 4320000, "wall_seconds": 8640}

    def __init__(self, root, create=False):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        if create:
            exclusive_json(root / "limits.json", self.LIMIT)
        if json.loads((root / "limits.json").read_text()) != self.LIMIT:
            raise ValueError("Campaign limits changed")

    def begin(self, run_id):
        runs = [json.loads(p.read_text()) for p in self.root.glob("run-*.json")]
        if (
            len(runs) >= self.LIMIT["runs"]
            or sum(r["wall_reservation"] for r in runs) + BUDGET["wall_seconds"]
            > self.LIMIT["wall_seconds"]
        ):
            raise ValueError("Campaign run/wall ceiling exhausted")
        if any(r["run_id"] == run_id for r in runs):
            raise ValueError("Campaign run already claimed")
        exclusive_json(
            self.root / f"run-{len(runs):04d}.json",
            {"run_id": run_id, "wall_reservation": BUDGET["wall_seconds"]},
        )

    def charge(self, run_id, reservation=0):
        if not any(
            json.loads(p.read_text())["run_id"] == run_id for p in self.root.glob("run-*.json")
        ):
            raise ValueError("Unclaimed campaign run")
        entries = [json.loads(p.read_text()) for p in sorted(self.root.glob("charge-*.json"))]
        used = sum(e["reserved_tokens"] for e in entries)
        ids = {e["run_id"] for e in entries} | {run_id}
        if (
            len(ids) > self.LIMIT["runs"]
            or len(entries) >= self.LIMIT["requests"]
            or used + reservation > self.LIMIT["reserved_tokens"]
        ):
            raise ValueError("Campaign-wide ceiling exhausted")
        exclusive_json(
            self.root / f"charge-{len(entries):04d}.json",
            {"run_id": run_id, "reserved_tokens": reservation, "at": historical.now()},
        )


async def generate(spec, config, coordinate, frozen, folder, campaign, provider=None):
    campaign.begin(coordinate["id"])
    journal = historical.Journal(folder, coordinate["id"])
    start = time.monotonic()
    workspace = Workspace(spec, frozen["body"]["image_id"])
    journal.append(
        "context",
        {
            "coordinate": coordinate,
            "freeze_hash": frozen["hash"],
            "configuration": config,
            "source_hashes": workspace.hashes(),
        },
    )
    owned = provider is None
    if owned:
        provider = NvidiaProvider(
            ProviderSettings(
                chat_model=config["model"],
                provider_retries=0,
                provider_max_requests=BUDGET["requests"],
                provider_timeout_seconds=BUDGET["provider_timeout_seconds"],
            )
        )
    assert provider is not None
    requests = reserved = retries = 0
    history = []
    status, error = "request_budget_exhausted", None
    payload, retry_of = None, None
    try:
        while requests < BUDGET["requests"]:
            remaining = BUDGET["wall_seconds"] - (time.monotonic() - start)
            if remaining <= 0:
                status = "generation_timeout"
                break
            if retry_of is None:
                payload = {
                    **config["parameters"],
                    "model": config["model"],
                    "messages": messages(workspace, history, requests, reserved),
                }
            assert payload is not None
            size = sum(len(m["content"].encode()) for m in payload["messages"])
            reservation = size + payload["max_tokens"]
            if (
                size > BUDGET["input_bytes_per_request"]
                or reserved + reservation > BUDGET["token_upper_bound"]
            ):
                status = "token_budget_exhausted"
                break
            try:
                campaign.charge(coordinate["id"], reservation)
            except ValueError:
                status = "campaign_budget_exhausted"
                break
            requests += 1
            reserved += reservation
            journal.append(
                "request",
                {
                    "payload": payload,
                    "request_hash": identity(payload),
                    "request_index": requests,
                    "retry_of": retry_of,
                    "reserved_tokens": reservation,
                },
            )
            try:
                body = await asyncio.wait_for(
                    provider.request(
                        "chat", "https://integrate.api.nvidia.com/v1/chat/completions", payload
                    ),
                    timeout=min(remaining, BUDGET["provider_timeout_seconds"] + 5),
                )
            except Exception as exc:
                call = dict(provider.calls[-1]) if provider.calls else {}
                error = {
                    "type": type(exc).__name__,
                    "code": getattr(exc, "code", None),
                    "request_index": requests,
                    "call": call,
                }
                transient = (
                    type(exc).__name__ == "TimeoutError"
                    or getattr(exc, "code", None) == "provider_unavailable"
                    or call.get("status") in (429, 500, 502, 503, 504)
                )
                can_retry = (
                    transient
                    and retries < BUDGET["automatic_retries"]
                    and requests < BUDGET["requests"]
                )
                journal.append("provider_error", {**error, "retry_planned": can_retry})
                if can_retry:
                    retries += 1
                    retry_of = requests
                    error = None
                    await asyncio.sleep(1)
                    continue
                status = "provider_failure"
                break
            retry_of = None
            # Sanitize values recursively without cutting the JSON envelope mid-string.
            safe = json.loads(json.dumps(body))

            def clean(value):
                if isinstance(value, str):
                    return sanitize_model_text(value, 200000)
                if isinstance(value, list):
                    return [clean(v) for v in value]
                if isinstance(value, dict):
                    return {k: clean(v) for k, v in value.items()}
                return value

            safe = clean(safe)
            journal.append("response", safe)
            try:
                action = decision(safe)
            except ValueError as exc:
                journal.append("invalid_decision", {"error": str(exc)})
                status = "invalid_output"
                break
            if (
                action == {"tool": "test"}
                and BUDGET["wall_seconds"] - (time.monotonic() - start) < 30
            ):
                journal.append(
                    "deadline", {"reason": "Insufficient remaining wall for fixed ordinary tool"}
                )
                status = "generation_timeout"
                break
            workspace.feedback_seen = True
            before = workspace.hashes()
            try:
                value = await asyncio.to_thread(workspace.action, action)
                output = {
                    "action": action,
                    "result": value,
                    "before": before,
                    "after": workspace.hashes(),
                }
            except (ValueError, TypeError, KeyError) as exc:
                output = {
                    "action": action,
                    "error": str(exc),
                    "before": before,
                    "after": workspace.hashes(),
                }
            history.append(output)
            journal.append("tools", output)
            if workspace.submitted:
                status = "submitted"
                break
    except Exception as exc:
        status = "infrastructure_failure"
        error = {"type": type(exc).__name__}
        journal.append("infrastructure_error", error)
    finally:
        if owned:
            await provider.close()
    terminal = {
        "status": status,
        "error": error,
        "requests": requests,
        "reserved_tokens": reserved,
        "retries": retries,
        "counts": workspace.counts,
        "source_hashes": workspace.hashes(),
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }
    journal.append("terminal", terminal)
    record = {
        "id": coordinate["id"],
        "coordinate": coordinate,
        "freeze_hash": frozen["hash"],
        "configuration_hash": identity(config),
        "context_hash": identity(historical.context(spec)),
        "generation_status": status,
        "error": error,
        "requests": requests,
        "token_reservation_upper_bound": reserved,
        "retries": retries,
        "counts": workspace.counts,
        "generation_wall_ms": terminal["elapsed_ms"],
        "ordinary_tool_ms": workspace.test_ms,
        "events_count": journal.sequence,
        "events_head": journal.head,
        "provider_calls": provider.calls,
        "candidate_id": None,
    }
    if workspace.submitted:
        candidate = {
            "id": coordinate["id"],
            "task_id": spec["id"],
            "spec_hash": spec["spec_hash"],
            "kind": "agent",
            "label": config["label"] + " · trial " + str(coordinate["trial"]),
            "producer": config["model"],
            "experiment_id": frozen["body"]["id"],
            "trial_id": coordinate["id"],
            "edits": workspace.edits,
            "freeze_hash": frozen["hash"],
            "events_head": journal.head,
            "configuration_hash": identity(config),
            "provenance": "Genuine bounded source/tool producer; no independent feedback.",
        }
        candidate["candidate_hash"] = build_candidate(spec, candidate)["candidate_hash"]
        record["candidate_id"] = candidate["id"]
        record["candidate_hash"] = candidate["candidate_hash"]
        exclusive_json(folder / "candidate.json", candidate)
    exclusive_json(folder / "generation.json", record)
    return record
