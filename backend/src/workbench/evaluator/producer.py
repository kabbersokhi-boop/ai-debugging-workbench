"""Trusted JSON tool loop. No producer shell, host working directory, or scoring access.

The namespace is an in-memory copy of approved source/ordinary tests. Candidate Python runs
only through the unchanged networkless M1 container adapter. Provider credentials stay here.
"""

import ast
import asyncio
import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from workbench.config import ProviderSettings
from workbench.evaluator.catalog import apply, digest, identity
from workbench.evaluator.experiment_catalog import build_candidate, exclusive_json
from workbench.evaluator.runner import execute
from workbench.rag.provider import NvidiaProvider, sanitize_model_text

HARNESS = "json-source-tools-v2"
PROMPT = """You are repairing an upstream Python library. You have the SAME source-inspection,
edit, and ordinary-test tools as every compared configuration. No shell or external retrieval.
Return one JSON object: {"decision":"brief explanation", "actions":[...]}.
Tools (use exact fields; the file path belongs INSIDE each edit):
{"tool":"read","path":"allowed file","start":1,"end":100} (1-based, <=120 lines)
{"tool":"search","query":"literal text"} (all approved files; <=20 hits)
{"tool":"edit","edits":[{"path":"allowed production path","old":"exact text","new":"replacement"}]}
{"tool":"test"} (fixed ordinary upstream command; current source, fresh isolated container)
{"tool":"submit"} (submit current source as final; must have edited and run tests after last edit).
At most four actions per response. Read/search/test results arrive as a user tool-results message.
Only production paths may be edited; tests are available for reading and execution, never editing.
Use source inspection as needed, implement a legitimate correction, run ordinary tests, and revise
if they fail within the stated budgets. Passing ordinary tests does not prove correctness.
You are not given reference fixes or independent checks. Preserve documented behavior and consider
edge cases in the public problem. Submit when ready. No markdown fences around the JSON.
"""
BUDGET = {
    "requests": 12,
    "output_tokens_per_request": 3000,
    "token_upper_bound": 180000,
    "wall_seconds": 420,
    "provider_timeout_seconds": 60,
    "revisions": 4,
    "ordinary_runs": 4,
    "read_search_actions": 16,
    "actions_per_response": 4,
    "automatic_retries": 0,
    "source_read_chars": 12000,
}


def now():
    return datetime.now(UTC).isoformat()


def context(spec):
    symbols = spec.get(
        "producer_symbols",
        ["bucket"] if spec["id"] == "more-bucket" else ["OrderedMultiDict.addlist"],
    )
    excerpts = []
    for path in spec["allowed_paths"]:
        source = spec["files"][path]
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                nodes = [(node.name, node)]
                if isinstance(node, ast.ClassDef):
                    nodes += [
                        (node.name + "." + m.name, m)
                        for m in node.body
                        if isinstance(m, ast.FunctionDef)
                    ]
                for name, selected in nodes:
                    if name in symbols:
                        excerpts.append(
                            {
                                "path": path,
                                "symbol": name,
                                "start": selected.lineno,
                                "end": selected.end_lineno,
                                "content": "".join(
                                    source.splitlines(True)[
                                        selected.lineno - 1 : selected.end_lineno
                                    ]
                                ),
                            }
                        )
    return {
        "project": spec["project"],
        "base_commit": spec["base_commit"],
        "problem": spec["problem"],
        "expected_behavior": spec["expected"],
        "allowed_paths": spec["allowed_paths"],
        "files": {
            p: {"lines": len(v.splitlines()), "sha256": digest(v)} for p, v in spec["files"].items()
        },
        "ordinary_command": spec["ordinary"],
        "environment": (
            "Python 3.12.14, pytest 8.3.5; no network; read-only source; "
            "fixed installed dependencies"
        ),
        "source_excerpts": excerpts,
        "budget": BUDGET,
    }


class Journal:
    def __init__(self, folder: Path, trial_id: str):
        self.folder, self.trial_id = folder, trial_id
        folder.mkdir(parents=True, exist_ok=True)
        # Exclusive claim before any request: same trial can never be resumed/retried in place.
        exclusive_json(folder / "claim.json", {"trial_id": trial_id, "claimed_at": now()})
        self.sequence = 0
        self.head = "0" * 64

    def append(self, kind: str, payload):
        body = {
            "trial_id": self.trial_id,
            "sequence": self.sequence,
            "previous_hash": self.head,
            "at": now(),
            "kind": kind,
            "payload": payload,
        }
        self.head = identity(body)
        exclusive_json(self.folder / f"event-{self.sequence:04d}.json", {**body, "hash": self.head})
        self.sequence += 1


class Workspace:
    def __init__(self, spec, image_id):
        self.spec, self.image_id = spec, image_id
        self.files = dict(spec["files"])
        self.edits: list[dict[str, str]] = []
        self.counts = {"revisions": 0, "ordinary_runs": 0, "read_search_actions": 0}
        self.tested_hash: str | None = None
        self.test_ms = 0
        self.submitted = False
        self.feedback_seen = True
        self.last_test_failed = False

    def hashes(self):
        return {p: digest(v) for p, v in self.files.items()}

    def action(self, action: dict[str, Any]):
        tool = action.get("tool")
        if tool == "edit" and set(action) == {"tool", "path", "edits"}:
            # Accept the common file-level spelling too; both normalize to exact allowlisted edits.
            action = {
                "tool": "edit",
                "edits": [{"path": action["path"], **edit} for edit in action["edits"]],
            }
        fields = {
            "read": {"tool", "path", "start", "end"},
            "search": {"tool", "query"},
            "edit": {"tool", "edits"},
            "test": {"tool"},
            "submit": {"tool"},
        }
        if tool not in fields or set(action) != fields[tool] or self.submitted:
            raise ValueError(
                "Unsupported tool contract. "
                'Edit example: {"tool":"edit","edits":[{"path":"file.py",'
                '"old":"exact source","new":"replacement"}]}'
            )
        if tool in ("read", "search"):
            if self.counts["read_search_actions"] >= BUDGET["read_search_actions"]:
                raise ValueError("Read/search budget exhausted")
            self.counts["read_search_actions"] += 1
        if tool == "read":
            path, start, end = action["path"], action["start"], action["end"]
            if path not in self.files:
                raise ValueError("Path outside approved source namespace")
            if (
                type(start) is not int
                or type(end) is not int
                or start < 1
                or end < start
                or end - start >= 120
            ):
                raise ValueError("Read bounds invalid; maximum 120 lines")
            text = "".join(
                f"{n}: {v}\n"
                for n, v in enumerate(self.files[path].splitlines(), 1)
                if start <= n <= end
            )
            return {
                "path": path,
                "text": text[: BUDGET["source_read_chars"]],
                "truncated": len(text) > BUDGET["source_read_chars"],
            }
        if tool == "search":
            query = action["query"]
            if not isinstance(query, str) or not query or len(query) > 200:
                raise ValueError("Search requires a bounded literal")
            hits = [
                {"path": p, "line": n, "text": line[:240]}
                for p, v in self.files.items()
                for n, line in enumerate(v.splitlines(), 1)
                if query in line
            ]
            return {"hits": hits[:20], "truncated": len(hits) > 20}
        if tool in ("edit", "test", "submit") and self.last_test_failed and not self.feedback_seen:
            raise ValueError("Ordinary checks failed this turn. Inspect feedback on the next turn.")
        if tool == "edit":
            if self.counts["revisions"] >= BUDGET["revisions"]:
                raise ValueError("Revision budget exhausted")
            edits = action["edits"]
            if not isinstance(edits, list) or not edits or len(edits) + len(self.edits) > 12:
                raise ValueError("Edit budget exceeded")
            # Atomic admission of the entire revision against the current working source.
            updated = apply({**self.spec, "files": self.files}, edits)
            self.files = updated
            self.edits += edits
            self.counts["revisions"] += 1
            return {"status": "applied", "source_hashes": self.hashes()}
        if tool == "test":
            if self.counts["ordinary_runs"] >= BUDGET["ordinary_runs"]:
                raise ValueError("Ordinary-test budget exhausted")
            self.counts["ordinary_runs"] += 1
            record = execute(self.files, self.spec["ordinary"], self.image_id, threading.Event())
            self.tested_hash = identity(self.hashes())
            self.last_test_failed = record.get("exit_code") != 0
            self.feedback_seen = not self.last_test_failed
            self.test_ms += record["duration_ms"]
            return record
        if self.last_test_failed and not self.feedback_seen:
            raise ValueError(
                "Ordinary checks failed this turn. Inspect their feedback on the next turn "
                "before revising or submitting."
            )
        if not self.edits or self.tested_hash != identity(self.hashes()):
            raise ValueError(
                "Edit and run ordinary tests after the last revision before submitting"
            )
        self.submitted = True
        return {"status": "submitted", "source_hashes": self.hashes()}


async def generate(spec, config, coordinate, frozen, folder, provider=None):
    trial_id = coordinate["id"]
    journal = Journal(folder, trial_id)
    start = time.monotonic()
    workspace = Workspace(spec, frozen["body"]["image_id"])
    initial = context(spec)
    messages = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": json.dumps(initial)},
    ]
    journal.append(
        "context",
        {
            "messages": messages.copy(),
            "context_hash": identity(initial),
            "coordinate": coordinate,
            "freeze_hash": frozen["hash"],
            "configuration": config,
            "harness_source_hash": digest(await asyncio.to_thread(Path(__file__).read_bytes)),
            "source_hashes": workspace.hashes(),
        },
    )
    owned = provider is None
    requests = reserved = 0
    status = "no_usable_candidate"
    error = None
    try:
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
        while requests < BUDGET["requests"]:
            outputs: list[dict[str, Any]] = []
            remaining = BUDGET["wall_seconds"] - (time.monotonic() - start)
            if remaining <= 0:
                status = "generation_timeout"
                break
            payload = {
                "model": config["model"],
                "messages": messages,
                "temperature": config["temperature"],
                "max_tokens": BUDGET["output_tokens_per_request"],
                "response_format": {"type": "json_object"},
            }
            # UTF-8 bytes conservatively bound input tokens; reserve maximum output even on errors.
            input_bytes = sum(len(m["content"].encode()) for m in messages)
            reservation = input_bytes + payload["max_tokens"]
            if reserved + reservation > BUDGET["token_upper_bound"]:
                status = "token_budget_exhausted"
                break
            reserved += reservation
            requests += 1
            journal.append(
                "request",
                {
                    "request_hash": identity(payload),
                    "messages_hash": identity(messages),
                    "parameters": {k: v for k, v in payload.items() if k != "messages"},
                    "input_bytes_upper_bound": input_bytes,
                    "reserved_tokens": reservation,
                    "request_index": requests,
                },
            )
            body = await asyncio.wait_for(
                provider.request(
                    "chat", "https://integrate.api.nvidia.com/v1/chat/completions", payload
                ),
                timeout=min(remaining, BUDGET["provider_timeout_seconds"]),
            )
            safe_body = json.loads(sanitize_model_text(json.dumps(body), 200000))
            journal.append("response", safe_body)
            choice = body["choices"][0]
            raw = choice["message"]["content"]
            if choice.get("finish_reason") != "stop" or not isinstance(raw, str):
                status = "invalid_output"
                break
            messages.append({"role": "assistant", "content": raw})
            try:
                decision = json.loads(raw)
                actions = decision["actions"]
                if (
                    not isinstance(actions, list)
                    or not 1 <= len(actions) <= BUDGET["actions_per_response"]
                    or any(not isinstance(a, dict) for a in actions)
                ):
                    raise ValueError("Response must contain one to four tool actions")
            except (ValueError, KeyError, TypeError):
                # Invalid responses consume requests and receive standard protocol feedback.
                actions = []
                outputs = [
                    {"error": "Invalid JSON action protocol; return one object with actions"}
                ]
            else:
                outputs = []
            workspace.feedback_seen = True
            for action in actions:
                if error is not None:
                    outputs.append(
                        {
                            "action": action,
                            "error": "Infrastructure failure before action",
                            "before": workspace.hashes(),
                            "after": workspace.hashes(),
                        }
                    )
                    continue
                if time.monotonic() - start >= BUDGET["wall_seconds"]:
                    status = "generation_timeout"
                    outputs.append(
                        {
                            "action": action,
                            "error": "Wall budget exhausted before action",
                            "before": workspace.hashes(),
                            "after": workspace.hashes(),
                        }
                    )
                    continue
                before = workspace.hashes()
                try:
                    value = await asyncio.to_thread(workspace.action, action)
                    outputs.append(
                        {
                            "action": action,
                            "result": value,
                            "before": before,
                            "after": workspace.hashes(),
                        }
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    outputs.append(
                        {
                            "action": action,
                            "error": str(exc),
                            "before": before,
                            "after": workspace.hashes(),
                        }
                    )
                except Exception as exc:
                    error = {"type": type(exc).__name__, "code": None}
                    status = "infrastructure_failure"
                    outputs.append(
                        {
                            "action": action,
                            "execution_error": error,
                            "before": before,
                            "after": workspace.hashes(),
                        }
                    )
            tool_message = {
                "role": "user",
                "content": json.dumps(
                    {
                        "tool_results": outputs,
                        "requests_remaining": BUDGET["requests"] - requests,
                        "budget_used": workspace.counts,
                        "instruction": (
                            "Use remaining tools to correct ordinary failures, then submit. "
                            "Last request must submit."
                        ),
                    }
                ),
            }
            journal.append("tools", {"message": tool_message, "source_hashes": workspace.hashes()})
            messages.append(tool_message)
            if error is not None:
                journal.append("error", error)
                break
            if workspace.submitted:
                status = "submitted"
                break
        if status == "no_usable_candidate":
            status = "request_budget_exhausted"
    except Exception as exc:
        status = (
            "provider_failure"
            if type(exc).__name__ in ("ProviderError", "TimeoutError")
            else "infrastructure_failure"
        )
        error = {"type": type(exc).__name__, "code": getattr(exc, "code", None)}
        journal.append("error", error)
    finally:
        if owned and provider is not None:
            await provider.close()
    journal.append(
        "terminal",
        {
            "status": status,
            "error": error,
            "requests": requests,
            "reserved_tokens": reserved,
            "source_hashes": workspace.hashes(),
            "counts": workspace.counts,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        },
    )
    record: dict[str, Any] = {
        "id": trial_id,
        "coordinate": coordinate,
        "freeze_hash": frozen["hash"],
        "configuration_hash": identity(config),
        "context_hash": identity(initial),
        "generation_status": status,
        "error": error,
        "requests": requests,
        "token_reservation_upper_bound": reserved,
        "provider_calls": list(provider.calls) if provider is not None else [],
        "counts": workspace.counts,
        "generation_wall_ms": round((time.monotonic() - start) * 1000),
        "ordinary_tool_ms": workspace.test_ms,
        "events_count": journal.sequence,
        "events_head": journal.head,
        "candidate_id": None,
    }
    if workspace.submitted:
        c = {
            "id": trial_id,
            "task_id": spec["id"],
            "spec_hash": spec["spec_hash"],
            "kind": "agent",
            "label": config["label"] + " · trial " + str(coordinate["trial"]),
            "producer": config["model"],
            "experiment_id": frozen["body"]["id"],
            "trial_id": trial_id,
            "provenance": (
                "Genuine interactive model/harness trial. Same approved source and "
                "ordinary tools; no independent or reference feedback. Public historical "
                "task; contamination unknown."
            ),
            "edits": workspace.edits,
            "freeze_hash": frozen["hash"],
            "generation": "trials/" + trial_id,
            "configuration_hash": identity(config),
            "events_head": journal.head,
        }
        full = build_candidate(spec, c)
        c["candidate_hash"] = full["candidate_hash"]
        record["candidate_id"], record["candidate_hash"] = trial_id, c["candidate_hash"]
        exclusive_json(folder / "candidate.json", c)
    exclusive_json(folder / "generation.json", record)
    return record
