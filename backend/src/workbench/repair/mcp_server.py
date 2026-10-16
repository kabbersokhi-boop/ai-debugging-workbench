"""Official MCP stdio server: a subprocess bound to one trusted repair context.

The launcher supplies UUIDs/URLs, never the model. It receives no DB/provider environment.
"""

import os
from uuid import UUID

import httpx
from mcp.server.fastmcp import FastMCP

from workbench.rag.snapshot import APPROVED_PATHS, load_snapshot
from workbench.repair.contracts import PatchProposal, apply_patch

mcp = FastMCP("approved-retail-repair", log_level="ERROR")
REPAIR_ID = str(UUID(os.environ["REPAIR_ID"]))
SNAPSHOT = load_snapshot()
if os.environ["SNAPSHOT_ID"] != SNAPSHOT.id:
    raise ValueError("MCP context does not match frozen snapshot")
BROKER = os.environ["REPAIR_BROKER_URL"]
CREATED: dict[str, int] = {}
ATTEMPTS = 0
READS = 0


def source(path: str):
    if path not in APPROVED_PATHS:
        raise ValueError("Source path is outside the approved frozen application")
    return next(f for f in SNAPSHOT.files if f.path == path)


@mcp.tool()
def search_source(query: str) -> dict:
    """Search approved frozen source, at most 8 matching lines. No workbench/test corpus."""
    global READS
    READS += 1
    if READS > 6 or not 1 <= len(query) <= 150:
        raise ValueError("Source tool budget exceeded")
    matches = []
    for file in SNAPSHOT.files:
        for n, line in enumerate(file.content.splitlines(), 1):
            if query.casefold() in line.casefold():
                matches.append({"path": file.path, "line": n, "content": line})
    return {"snapshot_id": SNAPSHOT.id, "matches": matches[:8], "strategy": "literal source search"}


@mcp.tool()
def read_source(path: str, start_line: int, end_line: int) -> dict:
    """Read an exact inclusive range (at most 80 lines) from the bound source snapshot."""
    global READS
    READS += 1
    if READS > 6:
        raise ValueError("Source tool budget exceeded")
    file = source(path)
    lines = file.content.splitlines()
    if not 1 <= start_line <= end_line <= len(lines) or end_line - start_line >= 80:
        raise ValueError("Invalid or oversized source range")
    return {
        "snapshot_id": SNAPSHOT.id,
        "source_commit": SNAPSHOT.source_commit,
        "path": path,
        "original_sha256": file.sha256,
        "start_line": start_line,
        "end_line": end_line,
        "content": "\n".join(lines[start_line - 1 : end_line]),
    }


async def broker_post(path: str, payload: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=65) as client:
            response = await client.post(BROKER + path, json=payload)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or "candidate_hash" not in body:
                raise ValueError("Invalid executor response")
            return body
    except (httpx.HTTPError, ValueError):
        return {
            "tool_error": {
                "kind": "execution",
                "message": (
                    "Candidate executor is unavailable or its fixed procedure failed. "
                    "No pass is inferred."
                ),
            }
        }


@mcp.tool()
async def apply_candidate(patch: PatchProposal) -> dict:
    """Validate an exact-text patch to cart.js, create a disposable candidate, max 2 attempts."""
    global ATTEMPTS
    ATTEMPTS += 1
    if ATTEMPTS > 2:
        raise ValueError("Candidate attempt budget exhausted")
    validated = apply_patch(SNAPSHOT, patch)
    result = await broker_post(
        "/candidates", {"repair_id": REPAIR_ID, "attempt": ATTEMPTS, "patch": patch.model_dump()}
    )
    if "tool_error" in result:
        return result
    if result["candidate_hash"] != validated["candidate_hash"]:
        return {"tool_error": {"kind": "execution", "message": "Executor candidate hash mismatch"}}
    CREATED[result["candidate_hash"]] = ATTEMPTS
    return result


@mcp.tool()
async def verify_candidate(candidate_hash: str) -> dict:
    """Request the fixed, independent pricing browser procedure for this run's candidate."""
    attempt = CREATED.get(candidate_hash)
    if attempt is None:
        raise ValueError("Candidate is not owned by this repair session")
    result = await broker_post(f"/candidates/{REPAIR_ID}/{attempt}/verify")
    if "tool_error" in result:
        return result
    if result["candidate_hash"] != candidate_hash:
        return {"tool_error": {"kind": "execution", "message": "Verifier candidate hash mismatch"}}
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
