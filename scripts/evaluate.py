"""Small, frozen live evaluation. Never imported by runtime retrieval or prompts."""

import argparse
import asyncio
import hashlib
import json
import statistics
import time
from pathlib import Path

import httpx
from workbench.config import ProviderSettings, settings
from workbench.contracts import BUG
from workbench.rag.contracts import ContextChunk
from workbench.rag.diagnosis import diagnose, model_input
from workbench.rag.provider import NvidiaProvider, ProviderError
from workbench.rag.retrieval import RepositoryRetriever
from workbench.rag.snapshot import load_snapshot


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    snapshot = load_snapshot()
    suite = json.loads(Path("evals/retrieval-smoke.json").read_text())
    assert suite["snapshot_id"] == snapshot.id
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"http://127.0.0.1:8010/api/runs/{args.run_id}")
        response.raise_for_status()
        run = response.json()
    assert run["result"]["fixture_sha256"] == snapshot.fixture_sha256
    evidence = {
        "reproduction_status": run["status"],
        **{
            key: run["result"][key]
            for key in ["baseline", "observed", "checks", "fixture_sha256"]
        },
    }
    results = []
    for method in ["lexical", "dense", "hybrid", "hybrid_rerank"]:
        for query in suite["queries"]:
            provider = NvidiaProvider(ProviderSettings())
            try:
                retriever = RepositoryRetriever(provider)
                index_id = await retriever.index(snapshot)
                trace = await retriever.retrieve(
                    snapshot,
                    index_id,
                    query["query"],
                    method,
                    settings.context_token_budget,
                )
                relevant = set(query["relevant"])
                top = [c.source_id for c in trace.candidates[:5]]
                selected = {c.source_id for c in trace.supplied_context}
                rank = next(
                    (
                        i + 1
                        for i, c in enumerate(trace.candidates)
                        if c.source_id in relevant
                    ),
                    None,
                )
                results.append(
                    {
                        "method": method,
                        "query_id": query["id"],
                        "group": query["group"],
                        "recall_at_5": len(relevant & set(top)) / len(relevant)
                        if relevant
                        else None,
                        "precision_at_5": len(relevant & set(top)) / len(top)
                        if top
                        else 0,
                        "reciprocal_rank": 1 / rank if rank else 0,
                        "selected_recall": len(relevant & selected) / len(relevant)
                        if relevant
                        else None,
                        "retrieval": trace.model_dump(),
                        "provider_calls": provider.calls,
                    }
                )
            finally:
                await provider.close()
    whole = [
        ContextChunk(
            source_id=hashlib.sha256(
                f"whole:{snapshot.id}:{source.path}".encode()
            ).hexdigest()[:16],
            path=source.path,
            start_line=1,
            end_line=len(source.content.splitlines()),
            symbol="whole file",
            content=source.content.rstrip("\n"),
        )
        for source in snapshot.files
    ]
    progress = Path("artifacts/milestone-02/retrieval-measurements.json")
    progress.write_text(json.dumps(results, indent=2))
    diagnoses = []
    for task_id, report in [
        ("single-cart-defect", BUG.report),
        ("no-payment-backend", suite["queries"][6]["query"]),
    ]:
        for mode in ["retrieved", "whole_target"]:
            provider = NvidiaProvider(ProviderSettings())
            started = time.monotonic()
            try:
                if mode == "retrieved":
                    retriever = RepositoryRetriever(provider)
                    index_id = await retriever.index(snapshot)
                    trace = await retriever.retrieve(
                        snapshot, index_id, report, budget=settings.context_token_budget
                    )
                    chunks = trace.supplied_context
                else:
                    chunks = whole
                inputs = model_input(report, evidence, chunks, snapshot.id)
                try:
                    output, raw = await diagnose(
                        provider, inputs, chunks, snapshot.id, snapshot.source_commit
                    )
                    error = None
                except ProviderError as failure:
                    output, raw = None, None
                    error = {"code": failure.code, "message": str(failure)}
                diagnoses.append(
                    {
                        "task": task_id,
                        "mode": mode,
                        "model": provider.chat_model,
                        "context_count": len(chunks),
                        "context_utf8_bytes": len(
                            inputs["repository_context"].encode()
                        ),
                        "latency_ms": round((time.monotonic() - started) * 1000),
                        "output": output,
                        "citation_ranges_valid": output is not None,
                        "error": error,
                        "provider_calls": provider.calls,
                        "model_input": inputs,
                        "raw_response": raw,
                    }
                )
                Path("artifacts/milestone-02/diagnosis-measurements.json").write_text(
                    json.dumps(diagnoses, indent=2)
                )
            finally:
                await provider.close()
    summary = {}
    for method in ["lexical", "dense", "hybrid", "hybrid_rerank"]:
        answerable = [
            r for r in results if r["method"] == method and r["recall_at_5"] is not None
        ]
        all_rows = [r for r in results if r["method"] == method]
        summary[method] = {
            "answerable_queries": len(answerable),
            "no_answer_queries": len(all_rows) - len(answerable),
            "mean_recall_at_5": statistics.fmean(r["recall_at_5"] for r in answerable),
            "mean_precision_at_5": statistics.fmean(
                r["precision_at_5"] for r in answerable
            ),
            "mean_reciprocal_rank": statistics.fmean(
                r["reciprocal_rank"] for r in answerable
            ),
            "mean_selected_recall": statistics.fmean(
                r["selected_recall"] for r in answerable
            ),
            "mean_latency_ms": statistics.fmean(
                r["retrieval"]["latency_ms"] for r in all_rows
            ),
        }
    payload = {
        "mode": "live_nvidia",
        "snapshot_id": snapshot.id,
        "source_commit": snapshot.source_commit,
        "corpus_files": len(snapshot.files),
        "corpus_utf8_bytes": sum(len(f.content.encode()) for f in snapshot.files),
        "query_count": len(suite["queries"]),
        "independent_defect_count": 1,
        "summary": summary,
        "retrieval_results": results,
        "diagnosis_comparisons": diagnoses,
        "cost": {
            "verified_dollar_cost": None,
            "reason": "Provider pricing/billing unavailable; token usage is measured, not a dollar estimate.",
        },
        "limits": "One sample per condition; no general debugging accuracy claim. No-answer retrieval still returns candidates; model abstention is checked separately.",
    }
    target = Path("artifacts/milestone-02/evaluation.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2))
    print(
        json.dumps(
            {
                "summary": summary,
                "diagnoses": [
                    {
                        "task": d["task"],
                        "mode": d["mode"],
                        "outcome": d["output"]["outcome"]
                        if d["output"]
                        else d["error"]["code"],
                        "latency_ms": d["latency_ms"],
                    }
                    for d in diagnoses
                ],
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
