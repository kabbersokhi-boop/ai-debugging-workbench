"""M2 allowlist; the accepted M1 catalog and verifier sources remain unchanged."""

import difflib
import json
from typing import Any

from workbench.evaluator import catalog

ROOT = catalog.CATALOG / "experiments" / "m02-v1"
TASK_IDS = (*catalog.TASK_IDS, "more-seekable", "boltons-indexedset")
EXPERIMENT_ID = "m02-v1"


def task(task_id: str) -> dict[str, Any]:
    if task_id in catalog.TASK_IDS:
        return catalog.task(task_id)
    if task_id not in TASK_IDS:
        raise ValueError("Unsupported comparison task")
    folder = ROOT / "tasks" / task_id
    manifest = json.loads((folder / "manifest.json").read_text())
    files = {
        p: (folder / "source" / p).read_bytes().decode("utf-8") for p in manifest["source_files"]
    }
    if {p: catalog.digest(v) for p, v in files.items()} != manifest["source_files"]:
        raise ValueError("Comparison source integrity failure")
    return {**manifest, "spec_hash": catalog.identity(manifest), "files": files}


def build_candidate(spec: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    files = catalog.apply(spec, record["edits"])
    patch = "".join(
        "".join(
            difflib.unified_diff(
                spec["files"][p].splitlines(True),
                files[p].splitlines(True),
                fromfile="a/" + p,
                tofile="b/" + p,
            )
        )
        for p in spec["allowed_paths"]
    )
    binding = {
        "spec_hash": spec["spec_hash"],
        "patch_hash": catalog.digest(patch),
        "source_hashes": {p: catalog.digest(v) for p, v in files.items()},
    }
    computed = catalog.identity(binding)
    if record.get("candidate_hash", computed) != computed:
        raise ValueError("Comparison candidate integrity failure")
    return {
        **record,
        **binding,
        "candidate_hash": computed,
        "patch": patch,
        "files": files,
        "original": {p: spec["files"][p] for p in spec["allowed_paths"]},
        "modified": {p: files[p] for p in spec["allowed_paths"]},
    }


def candidate(candidate_id: str) -> dict[str, Any]:
    paths = {p.stem: p for p in (ROOT / "candidates").glob("*.json")}
    if candidate_id not in paths:
        raise ValueError("Unknown approved comparison candidate")
    record = json.loads(paths[candidate_id].read_text())
    spec = task(record["task_id"])
    if record["spec_hash"] != spec["spec_hash"]:
        raise ValueError("Comparison specification mismatch")
    return build_candidate(spec, record)


def freeze() -> dict[str, Any]:
    record = json.loads((ROOT / "freeze.json").read_text())
    if record["hash"] != catalog.identity(record["body"]):
        raise ValueError("Experiment freeze integrity failure")
    return record


def exclusive_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as file:
        file.write(json.dumps(value, indent=2) + "\n")
