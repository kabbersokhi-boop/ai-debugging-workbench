"""Narrow repair contracts. There are no commands, URLs or permissions in model arguments."""

import difflib
import hashlib
import json
from typing import Any, Literal

from pydantic import Field, model_validator

from workbench.rag.contracts import Snapshot, StrictModel
from workbench.rag.snapshot import validate_snapshot

CART_PATH = "fixtures/retail/cart.js"


class RemoteAction(StrictModel):
    action: Literal["reset", "add", "increase", "decrease"]


class Edit(StrictModel):
    old: str = Field(min_length=1, max_length=6000)
    new: str = Field(max_length=6000)


class PatchProposal(StrictModel):
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: Literal["fixtures/retail/cart.js"]
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    explanation: str = Field(min_length=5, max_length=1800)
    edits: list[Edit] = Field(min_length=1, max_length=3)


class ToolDecision(StrictModel):
    action: Literal["read_source", "search_source", "propose", "insufficient_evidence"]
    reason: str = Field(min_length=5, max_length=1500)
    path: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    query: str | None = Field(default=None, min_length=1, max_length=150)
    patch: PatchProposal | None = None

    @model_validator(mode="after")
    def required_arguments(self) -> "ToolDecision":
        if self.action == "propose" and self.patch is None:
            raise ValueError("propose requires patch")
        if self.action == "read_source" and (
            self.path is None or self.start_line is None or self.end_line is None
        ):
            raise ValueError("read_source requires path and inclusive line range")
        if self.action == "search_source" and self.query is None:
            raise ValueError("search_source requires query")
        return self


def sha256(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def apply_patch(snapshot: Snapshot, proposal: PatchProposal) -> dict[str, Any]:
    validate_snapshot(snapshot)
    source = next(f for f in snapshot.files if f.path == CART_PATH)
    if proposal.snapshot_id != snapshot.id or proposal.original_sha256 != source.sha256:
        raise ValueError("Stale base: patch must match the exact approved snapshot and file hash")
    if len(proposal.model_dump_json().encode()) > 14000:
        raise ValueError("Patch exceeds bounded proposal size")
    content = source.content
    for edit in proposal.edits:
        if content.count(edit.old) != 1:
            raise ValueError("Each old text must match exactly once; ambiguous or malformed change")
        if edit.old == edit.new:
            raise ValueError("No-op edit")
        content = content.replace(edit.old, edit.new, 1)
    if content == source.content or len(content.encode()) > 12000 or "\x00" in content:
        raise ValueError("Empty, unchanged or oversized candidate")
    patch_hash = sha256(json.dumps(proposal.model_dump(), sort_keys=True))
    candidate_hash = sha256(
        json.dumps({"snapshot": snapshot.id, "path": CART_PATH, "content": content}, sort_keys=True)
    )
    diff = "".join(
        difflib.unified_diff(
            source.content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{CART_PATH}",
            tofile=f"b/{CART_PATH}",
        )
    )
    return {
        "snapshot_id": snapshot.id,
        "source_commit": snapshot.source_commit,
        "original_sha256": source.sha256,
        "patch_hash": patch_hash,
        "candidate_hash": candidate_hash,
        "path": CART_PATH,
        "original": source.content,
        "content": content,
        "diff": diff,
        "proposal": proposal.model_dump(),
    }
