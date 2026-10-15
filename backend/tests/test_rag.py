"""Offline contracts/provider fixtures. These are not live NVIDIA evidence."""

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage
from langchain_core.prompt_values import ChatPromptValue
from pydantic import SecretStr

from workbench.config import ProviderSettings, Settings
from workbench.rag.contracts import Citation, ContextChunk, Diagnosis
from workbench.rag.diagnosis import model_input, validate_citations
from workbench.rag.provider import NvidiaProvider, ProviderError
from workbench.rag.retrieval import fuse, select_context
from workbench.rag.snapshot import APPROVED_PATHS, chunk_snapshot, load_snapshot, validate_snapshot


def test_snapshot_contains_only_approved_target_and_exact_line_grounded_chunks() -> None:
    snapshot = load_snapshot()
    assert {f.path for f in snapshot.files} == APPROVED_PATHS
    files = {f.path: f.content.splitlines() for f in snapshot.files}
    chunks = chunk_snapshot(snapshot)
    assert any(c.symbol == "calculateTotals" for c in chunks)
    assert any(c.symbol == "render" for c in chunks)
    for chunk in chunks:
        assert chunk.content == "\n".join(files[chunk.path][chunk.start_line - 1 : chunk.end_line])
        assert len(chunk.content.encode()) <= 1500


@pytest.mark.parametrize("change", ["path", "content", "commit", "digest"])
def test_snapshot_tampering_is_rejected(change: str) -> None:
    snapshot = load_snapshot().model_copy(deep=True)
    if change == "path":
        snapshot.files[0].path = "docs/reports/MILESTONE-01.md"
    elif change == "content":
        snapshot.files[0].content += "changed"
    elif change == "commit":
        snapshot.source_commit = "main"
    else:
        snapshot.fixture_sha256 = "0" * 64
    with pytest.raises(ValueError):
        validate_snapshot(snapshot)


def diagnosis(source_id: str = "source", start: int = 2, end: int = 4) -> Diagnosis:
    return Diagnosis(
        outcome="diagnosis",
        diagnosis="An offline fixture diagnosis.",
        citations=[Citation(source_id=source_id, start_line=start, end_line=end)],
        observations=["Offline test observation"],
        uncertainty=["Fixture only"],
        next_check="Inspect the source caller.",
    )


@pytest.mark.parametrize(
    "source,start,end", [("unseen", 2, 4), ("source", 1, 4), ("source", 2, 9), ("source", 4, 2)]
)
def test_citations_must_exist_inside_supplied_context(source: str, start: int, end: int) -> None:
    chunk = ContextChunk(
        source_id="source", path="cart.js", start_line=2, end_line=4, symbol="x", content="a\nb\nc"
    )
    with pytest.raises(ProviderError, match="outside its supplied context"):
        validate_citations(diagnosis(source, start, end), [chunk], "snapshot", "commit")


def test_valid_citations_bind_frozen_identity_and_insufficient_evidence_is_valid() -> None:
    chunk = ContextChunk(
        source_id="source", path="cart.js", start_line=2, end_line=4, symbol="x", content="a\nb\nc"
    )
    result = validate_citations(diagnosis(), [chunk], "snapshot", "commit")
    assert result["citations"][0]["snapshot_id"] == "snapshot"
    assert result["citations"][0]["path"] == "cart.js"
    insufficient = diagnosis().model_dump() | {"outcome": "insufficient_evidence", "citations": []}
    assert Diagnosis.model_validate(insufficient).outcome == "insufficient_evidence"


def test_rank_fusion_and_selection_record_actual_decisions() -> None:
    a = ContextChunk(
        source_id="a", path="cart.js", start_line=1, end_line=1, symbol="a", content="short"
    )
    b = a.model_copy(update={"source_id": "b", "content": "long" * 1000})
    candidates = fuse([a, b], [b, a])
    assert candidates[0].fusion_score == candidates[1].fusion_score
    selected = select_context(candidates, "snapshot", 300)
    assert [c.source_id for c in selected] == ["a"]
    assert candidates[0].selected and not candidates[1].selected
    assert "exceeds" in candidates[1].selection_reason


def test_actual_prompt_context_and_separators_stay_within_budget() -> None:
    chunk = ContextChunk(
        source_id="a", path="a.js", start_line=1, end_line=1, symbol="a", content="example"
    )
    other = chunk.model_copy(update={"source_id": "b"})
    budget = len(chunk.formatted("snapshot").encode()) + len(other.formatted("snapshot").encode())
    selected = select_context(fuse([chunk, other], []), "snapshot", budget)
    inputs = model_input("A report", {"status": "not_reproduced"}, selected, "snapshot")
    assert len(inputs["repository_context"].encode()) <= budget
    assert len(selected) == 1
    assert [m["role"] for m in inputs["messages"]] == ["system", "user"]


def config() -> ProviderSettings:
    return ProviderSettings(nvidia_api_key=SecretStr("offline-test-fixture"), provider_retries=1)


def test_missing_credentials_fail_closed_and_runner_settings_have_no_secret_field() -> None:
    with pytest.raises(ProviderError, match="Configure NVIDIA_API_KEY"):
        NvidiaProvider(ProviderSettings(nvidia_api_key=None))
    assert "nvidia_api_key" not in Settings.model_fields


async def test_http_failures_are_bounded_and_trace_does_not_contain_authorization() -> None:
    count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(503, json={"error": "offline fixture"})

    provider = NvidiaProvider(config(), httpx.MockTransport(handler))
    try:
        with pytest.raises(ProviderError, match="HTTP 503"):
            await provider.embed(["text"], "query")
        assert count == 2
        assert "offline-test-fixture" not in json.dumps(provider.calls)
        assert "Authorization" not in json.dumps(provider.calls)
    finally:
        await provider.close()


@pytest.mark.parametrize(
    "body",
    [
        {"data": []},
        {"data": [{"index": 1, "embedding": [1, 2]}]},
        {"choices": [{"finish_reason": "length", "message": {"content": "truncated"}}]},
    ],
)
async def test_invalid_provider_outputs_are_rejected(body: dict) -> None:
    provider = NvidiaProvider(
        config(), httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(ProviderError):
            if "choices" in body:
                await provider.chat(ChatPromptValue(messages=[HumanMessage(content="test")]))
            else:
                await provider.embed(["text"], "query")
    finally:
        await provider.close()
