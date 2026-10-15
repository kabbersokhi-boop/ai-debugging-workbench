"""Deterministic offline fixtures. These patches are never runtime repair answers."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import HumanMessage
from langchain_core.prompt_values import ChatPromptValue
from pydantic import ValidationError
from test_rag_integration import OfflineProvider

from workbench.config import ProviderSettings
from workbench.rag.diagnosis import diagnose, model_input
from workbench.rag.provider import NvidiaProvider, ProviderError, sanitize_model_text
from workbench.rag.snapshot import chunk_snapshot, load_snapshot
from workbench.repair.contracts import CART_PATH, Edit, PatchProposal, ToolDecision, apply_patch


def offline_patch(new: str = "sum + item.unitPriceCents * item.quantity") -> PatchProposal:
    source = next(f for f in load_snapshot().files if f.path == CART_PATH)
    return PatchProposal(
        snapshot_id=load_snapshot().id,
        path=CART_PATH,
        original_sha256=source.sha256,
        explanation="OFFLINE deterministic test fixture",
        edits=[Edit(old="sum + item.unitPriceCents", new=new)],
    )


def test_patch_binds_exact_source_and_hash_without_mutating_original():
    snapshot = load_snapshot()
    before = snapshot.model_dump_json()
    result = apply_patch(snapshot, offline_patch())
    assert len(result["candidate_hash"]) == 64
    assert result["candidate_hash"] != result["patch_hash"]
    assert "--- a/fixtures/retail/cart.js" in result["diff"]
    assert snapshot.model_dump_json() == before
    assert apply_patch(snapshot, offline_patch())["candidate_hash"] == result["candidate_hash"]
    assert (
        apply_patch(snapshot, offline_patch("sum + 1"))["candidate_hash"]
        != result["candidate_hash"]
    )


@pytest.mark.parametrize(
    "path",
    [
        "../cart.js",
        "/etc/passwd",
        "backend/src/workbench/repair/verifier.py",
        "fixtures/retail/../retail/cart.js",
        "fixtures/retail/index.html",
    ],
)
def test_patch_scope_rejects_paths(path):
    with pytest.raises(ValidationError):
        PatchProposal.model_validate(offline_patch().model_dump() | {"path": path})


@pytest.mark.parametrize(
    "change", ["snapshot", "hash", "old", "ambiguous", "noop", "null", "oversize"]
)
def test_patch_rejects_stale_or_malformed_changes(change):
    proposal = offline_patch()
    if change == "snapshot":
        proposal.snapshot_id = "a" * 64
    if change == "hash":
        proposal.original_sha256 = "b" * 64
    if change == "old":
        proposal.edits[0].old = "missing source text"
    if change == "ambiguous":
        proposal.edits[0].old = "const"
    if change == "noop":
        proposal.edits[0].new = proposal.edits[0].old
    if change == "null":
        proposal.edits[0].new = "\x00"
    if change == "oversize":
        proposal.edits = [Edit(old="const", new="x" * 6000)] * 3
    with pytest.raises(ValueError):
        apply_patch(load_snapshot(), proposal)


@pytest.mark.parametrize("action", ["propose", "read_source", "search_source"])
def test_model_decision_requires_tool_arguments(action):
    with pytest.raises(ValidationError):
        ToolDecision(action=action, reason="Offline fixture")


async def test_rejected_output_is_retained_before_schema_validation():
    snapshot = load_snapshot()
    chunks = chunk_snapshot(snapshot)[:1]
    retained = []

    class Offline(OfflineProvider):
        async def chat(self, prompt):
            return "not a structured diagnosis"

    async def save(text):
        retained.append(text)

    with pytest.raises(ProviderError) as error:
        await diagnose(
            Offline(),
            model_input("offline report", {}, chunks, snapshot.id),
            chunks,
            snapshot.id,
            snapshot.source_commit,
            save,
        )
    assert retained == ["not a structured diagnosis"]
    assert error.value.raw_response == retained[0]
    assert error.value.code == "invalid_model_output"


async def test_rejected_citations_retain_bounded_sanitized_model_text():
    snapshot = load_snapshot()
    chunks = chunk_snapshot(snapshot)[:1]
    raw = json.dumps(
        {
            "outcome": "diagnosis",
            "diagnosis": "Offline proposed cause.",
            "citations": [{"source_id": "unseen", "start_line": 1, "end_line": 2}],
            "observations": ["test"],
            "uncertainty": ["test"],
            "next_check": "Read source",
        }
    )

    class Offline(OfflineProvider):
        async def chat(self, prompt):
            return raw

    with pytest.raises(ProviderError) as error:
        await diagnose(
            Offline(),
            model_input("offline report", {}, chunks, snapshot.id),
            chunks,
            snapshot.id,
            snapshot.source_commit,
        )
    assert error.value.code == "invalid_citation"
    assert error.value.raw_response == raw
    secret = "nv" + "api-example-secret"
    assert secret not in sanitize_model_text(secret + "\nAuthorization: Bearer test-token")
    assert len(sanitize_model_text("é" * 30000).encode()) <= 24000


async def test_shared_request_output_budget_includes_transient_retries():
    from pydantic import SecretStr

    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(503)

    provider = NvidiaProvider(
        ProviderSettings(
            nvidia_api_key=SecretStr("offline-test"),
            provider_retries=1,
            model_output_token_limit=200,
        ),
        httpx.MockTransport(handler),
    )
    provider.output_budget_remaining = 200
    try:
        with pytest.raises(ProviderError) as error:
            await provider.chat(ChatPromptValue(messages=[HumanMessage(content="test")]))
        assert error.value.code == "output_budget" and count == 1
        assert provider.output_budget_remaining == 0
    finally:
        await provider.close()


async def test_evaluation_initializes_nonexistent_directory_and_saves_incrementally(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "offline_evaluator", Path("../scripts/evaluate.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "never-existed" / "output"
    assert not target.exists()
    folder = module.prepare_output(target)

    async def offline_provider_call():
        assert folder.is_dir()  # Directory exists before any provider work.
        return {"mode": "offline_fixture", "value": 1}

    rows = [await offline_provider_call()]
    module.save_measurements(folder, "retrieval-measurements.json", rows)
    rows.append({"mode": "offline_fixture", "value": 2})
    module.save_measurements(folder, "retrieval-measurements.json", rows)
    assert json.loads((folder / "retrieval-measurements.json").read_text()) == rows
    assert not list(folder.glob("*.tmp"))


async def test_truncated_chat_retains_actual_text_without_reusing_a_previous_response():
    from pydantic import SecretStr

    bodies = [
        {"choices": [{"finish_reason": "length", "message": {"content": "Actual truncated text"}}]},
        {"choices": []},
    ]
    provider = NvidiaProvider(
        ProviderSettings(nvidia_api_key=SecretStr("offline-test")),
        httpx.MockTransport(lambda _: httpx.Response(200, json=bodies.pop(0))),
    )
    try:
        prompt = ChatPromptValue(messages=[HumanMessage(content="Offline input")])
        with pytest.raises(ProviderError) as first:
            await provider.chat(prompt)
        assert first.value.raw_response == "Actual truncated text"
        with pytest.raises(ProviderError) as second:
            await provider.chat(prompt)
        assert second.value.raw_response is None
    finally:
        await provider.close()
