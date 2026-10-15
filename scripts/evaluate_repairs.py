"""Frozen bounded repair comparison. No reference fix is available to the graph.

uv run --project backend python scripts/evaluate_repairs.py --freeze
uv run --project backend python scripts/evaluate_repairs.py --live --split evaluation
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import httpx
from langgraph.checkpoint.memory import InMemorySaver
from playwright.async_api import async_playwright
from workbench.config import ROOT, ProviderSettings, settings
from workbench.rag.provider import NvidiaProvider, ProviderError
from workbench.rag.retrieval import RepositoryRetriever
from workbench.rag.snapshot import load_snapshot, scenario_manifest
from workbench.repair.graph import RepairGraph, RepairState
from workbench.repair.mcp_client import connect_tools
from workbench.repair.verifier import VERIFIER_VERSION

import docker

CONFIG = ROOT / "evals/experiment-v1.json"
OUTPUT = ROOT / "artifacts/evaluation-m4-v1"
CONDITIONS = ("one-shot-whole", "loop-whole", "loop-retrieval")
FROZEN_FILES = [
    "backend/src/workbench/config.py",
    "backend/src/workbench/contracts.py",
    "backend/src/workbench/rag/contracts.py",
    "backend/src/workbench/runner.py",
    "backend/src/workbench/repair/graph.py",
    "backend/src/workbench/repair/broker.py",
    "backend/src/workbench/repair/verifier.py",
    "backend/src/workbench/repair/contracts.py",
    "backend/src/workbench/repair/mcp_client.py",
    "backend/src/workbench/repair/mcp_server.py",
    "backend/src/workbench/rag/provider.py",
    "backend/src/workbench/rag/retrieval.py",
    "backend/src/workbench/rag/snapshot.py",
    "backend/src/workbench/rag/scenarios.json",
    "evals/final_checks.py",
    "evals/scenarios-v1.json",
    "scripts/evaluate_repairs.py",
    "docker/candidate_entry.py",
    "docker/candidate.Dockerfile",
    "backend/uv.lock",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docker_identity():
    client = docker.from_env()
    try:
        container = client.containers.get("ai-debugging-workbench-repair-broker-1")
        address = container.attrs["NetworkSettings"]["Networks"][
            "ai-debugging-workbench_repair-control"
        ]["IPAddress"]
        return f"http://{address}:8012", client.images.get("ai-debugging-candidate:milestone-03").id
    finally:
        client.close()


def frozen_config():
    _, image_id = docker_identity()
    client = docker.from_env()
    try:
        broker_image_id = client.containers.get("ai-debugging-workbench-repair-broker-1").attrs[
            "Image"
        ]
    finally:
        client.close()
    paths = [
        *FROZEN_FILES,
        *[
            str(p.relative_to(ROOT))
            for p in (ROOT / "backend/src/workbench/rag/scenarios").glob("*.json")
        ],
        "backend/src/workbench/rag/retail-snapshot.json",
    ]
    return {
        "experiment": f"retail-repair-comparison-{CONFIG.stem}",
        "scenario_version": "retail-scenarios-v1",
        "cases": scenario_manifest()["cases"],
        "conditions": list(CONDITIONS),
        "model": settings.chat_model,
        "embedding_model": settings.embedding_model,
        "rerank_model": settings.rerank_model,
        "temperature": 0,
        "thinking": False,
        "max_tokens_per_chat": 2000,
        "input_bound": settings.model_input_token_limit,
        "context_budget_utf8": settings.context_token_budget,
        "per_condition": {
            "one-shot-whole": {
                "decisions": 1,
                "patches": 1,
                "requests": 2,
                "feedback": "none before final scoring",
            },
            "loop-whole": {
                "decisions": 6,
                "patches": 2,
                "requests": 8,
                "feedback": "named retail-pricing-browser-v1 checks and patch validation only",
            },
            "loop-retrieval": {
                "decisions": 6,
                "patches": 2,
                "requests": 8,
                "feedback": "same as loop-whole",
            },
        },
        "shared_budget": {
            "http_requests_including_retries": 256,
            "reserved_output_tokens": 256000,
            "wall_seconds": 5400,
        },
        "case_timeout_seconds": 300,
        "provider_timeout_seconds": settings.provider_timeout_seconds,
        "retry_limit": settings.provider_retries,
        "candidate_runtime_image_id": image_id,
        "broker_image_id": broker_image_id,
        "verifier_version": VERIFIER_VERSION,
        "final_checks_version": "retail-final-v1",
        "scoring": (
            "final candidate only; issue-specific feedback check AND all feedback regression "
            "checks AND all evaluation-only final checks; "
            "infrastructure/invalid/timeouts count as unresolved"
        ),
        "diagnosis_input": (
            "No prior AI diagnosis in any condition; same report and observed failing "
            "check. This isolates repair loop and context effects."
        ),
        "checkpoint_mode": (
            "in-memory LangGraph for benchmark; atomically retained node states and "
            "raw responses on disk; product uses native PostgreSQL checkpoints"
        ),
        "cost": "unavailable; measured provider token usage only",
        "files": {path: digest(ROOT / path) for path in sorted(paths)},
    }


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str) + "\n")
    temporary.replace(path)


class BudgetTransport(httpx.AsyncBaseTransport):
    def __init__(self, ledger):
        self.ledger = ledger
        self.inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        budget = self.ledger
        tokens = json.loads(request.content).get("max_tokens", 0)
        if budget["http_requests"] >= 256 or budget["reserved_output_tokens"] + tokens > 256000:
            raise ProviderError("experiment_budget", "Frozen experiment budget exhausted")
        budget["http_requests"] += 1
        budget["reserved_output_tokens"] += tokens
        save(OUTPUT / "budget.json", budget)  # Charge before network, including failures.
        return await self.inner.handle_async_request(request)

    async def aclose(self):
        await self.inner.aclose()


async def final_score(broker_url, repair_id, attempt, output):
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(f"{broker_url}/candidates/{repair_id}/{attempt}/preview")
        response.raise_for_status()
        saved = await client.get(
            f"{broker_url}/candidates/{repair_id}/{attempt}/artifacts/candidate.json"
        )
        saved.raise_for_status()
        candidate = saved.json()
    docker_client = docker.from_env()
    try:
        container = docker_client.containers.list(
            filters={"label": f"ai-debugging-workbench.repair={repair_id}-{attempt}"}
        )[0]
        ip = next(iter(container.attrs["NetworkSettings"]["Networks"].values()))["IPAddress"]
        image = container.image
        if image is None:
            raise ValueError("Candidate runtime image unavailable")
        image_id = image.id
    finally:
        docker_client.close()
    if image_id != json.loads(CONFIG.read_text())["candidate_runtime_image_id"]:
        raise ValueError("Evaluation runtime changed")
    spec = importlib.util.spec_from_file_location(
        "evaluation_final_checks", ROOT / "evals/final_checks.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    snapshot = load_snapshot(candidate["snapshot_id"])

    async def served_hashes():
        hashes = {}
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            for source in snapshot.files:
                name = source.path.rsplit("/", 1)[-1]
                if name not in ("cart.js", "index.html", "styles.css"):
                    continue
                response = await client.get(
                    f"http://{ip}:8080/retail/{'' if name == 'index.html' else name}"
                )
                expected = candidate["content"] if name == "cart.js" else source.content
                if response.status_code != 200 or response.content != expected.encode():
                    raise ValueError("Final-check candidate bytes differ from approved identity")
                hashes[source.path] = hashlib.sha256(response.content).hexdigest()
        return hashes

    before = await served_hashes()
    async with asyncio.timeout(45), async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://{ip}:9223", timeout=10000)
        scored = await module.score(browser, output / "final.png")
    if before != await served_hashes():
        raise ValueError("Final-check source changed during execution")
    return {
        **scored,
        "candidate_hash": candidate["candidate_hash"],
        "source_snapshot": snapshot.id,
        "container_image_id": image_id,
        "executed_file_hashes": before,
        "final_checks_sha256": digest(ROOT / "evals/final_checks.py"),
    }


async def execute_case(case, condition, ledger, broker_url):
    output = OUTPUT / f"{case['id']}--{condition}"
    if (output / "result.json").exists():
        retained = json.loads((output / "result.json").read_text())
        if retained.get("configuration_sha256") != digest(CONFIG):
            raise ValueError("Saved result belongs to another experiment configuration")
        return retained
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG.read_text())
    limits = config["per_condition"][condition]
    provider = NvidiaProvider(
        ProviderSettings(provider_max_requests=12, model_output_token_limit=2000),
        BudgetTransport(ledger),
    )
    provider.output_budget_remaining = limits["requests"] * 2000
    repair_id = uuid4()
    state = {}
    started = time.monotonic()
    result = {
        "configuration_sha256": digest(CONFIG),
        "case": case["id"],
        "split": case["split"],
        "condition": condition,
        "mode": "offline_fixture" if provider.chat_model.startswith("offline-") else "live_nvidia",
        "repair_id": str(repair_id),
        "usable_candidate": False,
        "resolved": False,
        "issue_passed": False,
        "regression_passed": False,
        "final_passed": False,
    }
    try:
        async with asyncio.timeout(300), httpx.AsyncClient(timeout=65) as client:
            original = await client.post(
                broker_url + "/original/verify",
                params={"snapshot_id": case["snapshot_id"]},
            )
            original.raise_for_status()
            original_result = original.json()
            if (
                original_result.get("verifier_version") != config["verifier_version"]
                or original_result.get("container_image_id") != config["candidate_runtime_image_id"]
            ):
                raise ValueError(
                    "Original verification runtime binding differs from frozen experiment"
                )
            issue = next(c for c in original_result["checks"] if c["name"] == case["issue_check"])
            if issue["passed"]:
                raise ValueError("Scenario defect not detected by frozen issue check")
            snapshot = load_snapshot(case["snapshot_id"])
            if condition == "loop-retrieval":
                retriever = RepositoryRetriever(provider)
                index_id = await retriever.index(snapshot)
                trace = await retriever.retrieve(snapshot, index_id, case["report"], budget=4000)
                context = [c.model_dump() for c in trace.supplied_context]
                save(output / "retrieval.json", trace.model_dump())
            else:
                context = [f.model_dump() for f in snapshot.files]
            retrieval_calls = len(provider.calls)
            provider.config.provider_max_requests = provider.requests + limits["requests"]
            state = {
                "repair_id": str(repair_id),
                "run_id": str(uuid4()),
                "investigation_id": str(uuid4()),
                "snapshot_id": snapshot.id,
                "status": "queued",
                "evidence": {
                    "report": case["report"],
                    "browser": issue,
                    "diagnosis": {},
                    "context": context,
                },
                "source_reads": [],
                "model_records": [],
                "mcp_events": [],
                "attempts": [],
                "attempt_count": 0,
                "decision_count": 0,
                "request_remaining": limits["requests"],
                "output_budget_remaining": limits["requests"] * 2000,
                "deadline": (datetime.now(UTC) + timedelta(seconds=300)).isoformat(),
                "decision": None,
                "candidate_hash": None,
                "verification": None,
                "provider_calls": [],
                "error": None,
                "error_code": None,
                "original_verification": original_result,
            }

            async def retain(changes, title, detail):
                state.update(changes)
                save(
                    output / "partial.json",
                    {"state": state, "last_event": title, "detail": detail},
                )

            async with connect_tools(repair_id, snapshot.id, broker_url) as tools:
                graph = RepairGraph(
                    provider,
                    tools,
                    retain,
                    max_attempts=limits["patches"],
                    max_decisions=limits["decisions"],
                    max_requests=limits["requests"],
                ).compile(InMemorySaver())
                async for value in graph.astream(
                    cast(RepairState, state),
                    {
                        "configurable": {"thread_id": str(repair_id)},
                        "recursion_limit": 24,
                    },
                    stream_mode="values",
                ):
                    state = dict(value)
                    save(output / "partial.json", state)
                result["status"] = state["status"]
                attempts = state["attempts"]
                candidate = attempts[-1] if attempts else None
                result["usable_candidate"] = bool(candidate and candidate.get("candidate"))
                if candidate and candidate.get("verification"):
                    checks = candidate["verification"]["checks"]
                    result["issue_passed"] = next(
                        c["passed"] for c in checks if c["name"] == case["issue_check"]
                    )
                    result["regression_passed"] = all(c["passed"] for c in checks)
                    final = await final_score(broker_url, repair_id, candidate["number"], output)
                    save(output / "final-checks.json", final)
                    result["final_passed"] = final["status"] == "passed"
                    result["resolved"] = (
                        result["issue_passed"]
                        and result["regression_passed"]
                        and result["final_passed"]
                    )
            result["retrieval_http_calls"] = retrieval_calls
            result["context_utf8_bytes"] = len(json.dumps(context).encode())
    except Exception as error:
        result.update(
            status="infrastructure_error" if not isinstance(error, ProviderError) else error.code,
            error=type(error).__name__ + ": " + str(error)[:400],
        )
    finally:
        result.update(
            latency_ms=round((time.monotonic() - started) * 1000),
            attempts=state.get("attempt_count", 0),
            decisions=state.get("decision_count", 0),
            model_calls=sum(c["workload"] == "chat" for c in provider.calls),
            tool_calls=sum(c["method"] == "tools/call" for c in state.get("mcp_events", [])),
            provider_calls=provider.calls,
            state=state,
        )
        await provider.close()
        save(output / "result.json", result)
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(f"{broker_url}/repairs/{repair_id}/cleanup")
    return result


async def main(args):
    global CONFIG, OUTPUT
    if args.experiment:
        CONFIG = ROOT / args.experiment
    if args.output:
        OUTPUT = ROOT / args.output
    if args.freeze:
        if CONFIG.exists():
            raise SystemExit(
                "Frozen experiment already exists; create a versioned experiment to change it"
            )
        save(CONFIG, frozen_config())
        print("Frozen experiment written; commit it before held-out execution.")
        return
    if not args.live:
        raise SystemExit("Pass --live explicitly; this command makes real provider requests")
    config = json.loads(CONFIG.read_text())
    tracked = await asyncio.to_thread(
        subprocess.run,
        ["git", "diff", "--quiet", "HEAD", "--", str(CONFIG), *config["files"]],
        cwd=ROOT,
    )
    included = await asyncio.to_thread(
        subprocess.run,
        ["git", "ls-files", "--error-unmatch", str(CONFIG)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if tracked.returncode != 0 or included.returncode != 0:
        raise SystemExit("Commit the frozen configuration and implementation before live execution")
    if frozen_config() != config:
        raise SystemExit("Runtime/code/scenarios differ from the frozen configuration")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ledger = (
        json.loads((OUTPUT / "budget.json").read_text())
        if (OUTPUT / "budget.json").exists()
        else {
            "http_requests": 0,
            "reserved_output_tokens": 0,
            "deadline": (datetime.now(UTC) + timedelta(seconds=5400)).isoformat(),
            "configuration_sha256": digest(CONFIG),
        }
    )
    if ledger.get("configuration_sha256") != digest(CONFIG):
        raise SystemExit("Budget ledger belongs to a different experiment")
    broker_url, _ = docker_identity()
    async with httpx.AsyncClient(timeout=5) as client:
        health = (await client.get(broker_url + "/health")).json()
        if health["verifier_version"] != config["verifier_version"]:
            raise SystemExit("Broker image does not contain the frozen verifier")
    started = time.monotonic()
    results = []
    for case in config["cases"]:
        if case["split"] != args.split:
            continue
        for condition in CONDITIONS:
            if time.monotonic() - started > 5400:
                raise SystemExit("Experiment wall budget exhausted")
            result = await execute_case(case, condition, ledger, broker_url)
            results.append(result)
            save(OUTPUT / f"{args.split}-results.json", results)
            print(
                json.dumps(
                    {
                        k: result.get(k)
                        for k in (
                            "case",
                            "condition",
                            "status",
                            "resolved",
                            "model_calls",
                            "latency_ms",
                        )
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--experiment", help="Versioned configuration path; never overwrite a prior experiment"
    )
    parser.add_argument("--output", help="Separate result directory for the versioned experiment")
    parser.add_argument("--split", choices=["development", "evaluation"], default="evaluation")
    asyncio.run(main(parser.parse_args()))
