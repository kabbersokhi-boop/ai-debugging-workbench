"""Fixed task admission and immutable source/candidate identities. No executable uploads."""

import difflib
import hashlib
import json
from typing import Any

from workbench.config import ROOT

CATALOG = ROOT / "evaluation"
TASK_IDS = ("more-bucket", "boltons-addlist")


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def identity(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")))


def task(task_id: str) -> dict[str, Any]:
    if task_id not in TASK_IDS:
        raise ValueError("Unsupported task")
    folder = CATALOG / "tasks" / task_id
    manifest = json.loads((folder / "manifest.json").read_text())
    files = {}
    for name, expected in manifest["source_files"].items():
        content = (folder / "source" / name).read_bytes().decode("utf-8")
        if digest(content) != expected:
            raise ValueError("Pinned upstream source integrity failure")
        files[name] = content
    return {**manifest, "spec_hash": identity(manifest), "files": files}


def apply(task_spec: dict[str, Any], edits: list[dict[str, str]]) -> dict[str, str]:
    """Exact unique text edits; tests and any non-allowlisted files are ineligible."""
    if len(edits) > 12:
        raise ValueError("Patch exceeds edit budget")
    files = dict(task_spec["files"])
    for edit in edits:
        if set(edit) != {"path", "old", "new"}:
            raise ValueError("Invalid edit contract")
        path, old, new = edit["path"], edit["old"], edit["new"]
        if path not in task_spec["allowed_paths"]:
            raise ValueError("Unauthorized patch path; trusted files cannot be changed")
        if not old or files[path].count(old) != 1:
            raise ValueError("Patch does not apply uniquely to the pinned source")
        if len(new.encode()) > 24000:
            raise ValueError("Patch exceeds source budget")
        files[path] = files[path].replace(old, new, 1)
    return files


def candidate(candidate_id: str) -> dict[str, Any]:
    # Filesystem paths never come from an arbitrary client string.
    paths = {p.stem: p for p in (CATALOG / "candidates").glob("*.json")}
    if candidate_id not in paths:
        raise ValueError("Unknown approved candidate")
    record = json.loads(paths[candidate_id].read_text())
    spec = task(record["task_id"])
    if record["spec_hash"] != spec["spec_hash"]:
        raise ValueError("Candidate belongs to a different task specification")
    files = apply(spec, record["edits"])
    patch = "".join(
        "".join(
            difflib.unified_diff(
                spec["files"][p].splitlines(keepends=True),
                files[p].splitlines(keepends=True),
                fromfile="a/" + p,
                tofile="b/" + p,
            )
        )
        for p in spec["allowed_paths"]
    )
    binding = {
        "spec_hash": spec["spec_hash"],
        "patch_hash": digest(patch),
        "source_hashes": {p: digest(v) for p, v in files.items()},
    }
    if record["candidate_hash"] != identity(binding):
        raise ValueError("Candidate hash mismatch")
    return {
        **record,
        **binding,
        "patch": patch,
        "files": files,
        "original": {p: spec["files"][p] for p in spec["allowed_paths"]},
        "modified": {p: files[p] for p in spec["allowed_paths"]},
    }


def public_candidate(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if k != "files"}
