"""Strict, exact-context unified-diff subset, checked/applied by Git without executing source."""

import difflib
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from workbench.evaluator.catalog import digest, identity
from workbench.evaluator.experiment_catalog import task

MAX_PATCH_BYTES = 65536
MAX_SOURCE_BYTES = 1_500_000
HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:[^\r\n]*)\n")


def apply_patch(spec: dict[str, Any], patch: str) -> dict[str, str]:
    if not patch or len(patch.encode()) > MAX_PATCH_BYTES or "\x00" in patch or "\r" in patch:
        raise ValueError("Patch rejected: use a UTF-8, LF unified diff of at most 64 KiB")
    lines = patch.splitlines(keepends=True)
    files = dict(spec["files"])
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        git_header = None
        if lines[i].startswith("diff --git "):
            git_header = lines[i]
            i += 1
            if i < len(lines) and lines[i].startswith("index "):
                if not re.fullmatch(r"index [a-f0-9]+\.\.[a-f0-9]+(?: 100644)?\n", lines[i]):
                    raise ValueError("Patch rejected: unsupported index or file mode")
                i += 1
        if i + 1 >= len(lines) or not lines[i].startswith("--- a/"):
            raise ValueError("Patch rejected: only existing text-file unified diffs are supported")
        path = lines[i][6:].removesuffix("\n")
        if (
            path not in spec["allowed_paths"]
            or path in seen
            or lines[i + 1] != "+++ b/" + path + "\n"
            or (git_header is not None and git_header != f"diff --git a/{path} b/{path}\n")
        ):
            raise ValueError("Patch rejected: unauthorized, duplicate, renamed or unsafe path")
        seen.add(path)
        if len(seen) > 4:
            raise ValueError("Patch rejected: at most four production files")
        base = files[path].splitlines(keepends=True)
        result: list[str] = []
        cursor = 0
        new_cursor = 0
        i += 2
        hunks = 0
        while i < len(lines) and lines[i].startswith("@@ "):
            match = HUNK.fullmatch(lines[i])
            if not match:
                raise ValueError("Patch rejected: malformed hunk header")
            start, old_count, new_start, new_count = (
                int(match[1]),
                int(match[2] or 1),
                int(match[3]),
                int(match[4] or 1),
            )
            # Insertions use the preceding line number, including zero at file start.
            offset = start - 1 if old_count else start
            if offset < cursor or offset > len(base):
                raise ValueError("Patch rejected: overlapping or out-of-range hunk")
            result.extend(base[cursor:offset])
            new_cursor += offset - cursor
            if new_start != (new_cursor + 1 if new_count else new_cursor):
                raise ValueError("Patch rejected: stale or inconsistent new hunk position")
            i += 1
            old: list[str] = []
            new: list[str] = []
            while i < len(lines) and lines[i][:1] in (" ", "+", "-"):
                # A following file header belongs to the next file, not this hunk.
                if len(old) == old_count and len(new) == new_count:
                    break
                line = lines[i]
                if not line.endswith("\n"):
                    raise ValueError(
                        "Patch rejected: missing newline; no-newline markers unsupported"
                    )
                if line[0] in " -":
                    old.append(line[1:])
                if line[0] in " +":
                    new.append(line[1:])
                i += 1
            if (
                len(old) != old_count
                or len(new) != new_count
                or base[offset : offset + old_count] != old
            ):
                raise ValueError("Patch rejected: exact base/context mismatch or malformed hunk")
            if old == new:
                raise ValueError("Patch rejected: empty change")
            result.extend(new)
            cursor = offset + old_count
            new_cursor += new_count
            hunks += 1
            if hunks > 64:
                raise ValueError("Patch rejected: too many hunks")
        if not hunks:
            raise ValueError("Patch rejected: missing hunks")
        result.extend(base[cursor:])
        files[path] = "".join(result)
    if not seen or sum(len(v.encode()) for v in files.values()) > MAX_SOURCE_BYTES:
        raise ValueError("Patch rejected: source size limit")
    # Git is a second parser/applicator. No checkout, hooks, subprocess shell or Python imports.
    with tempfile.TemporaryDirectory(prefix="patch-audit-") as folder:
        for path in seen:
            target = Path(folder) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(spec["files"][path].encode())
        env = {"PATH": os.defpath, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
        for args in (["--check"], []):
            process = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", *args, "-"],
                input=patch.encode(),
                cwd=folder,
                env=env,
                capture_output=True,
                timeout=5,
            )
            if process.returncode:
                raise ValueError("Patch rejected by Git's unified-diff checks")
        if any((Path(folder) / path).read_bytes() != files[path].encode() for path in seen):
            raise ValueError("Patch rejected: application did not match exact-context admission")
    return files


def admit(task_id: str, patch: str, provenance: dict[str, Any]) -> dict[str, Any]:
    spec = task(task_id)
    files = apply_patch(spec, patch)
    canonical = "".join(
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
        "patch_hash": digest(canonical),
        "source_hashes": {p: digest(v) for p, v in files.items()},
    }
    body = {
        "version": "patch-audit-v1",
        "task_id": task_id,
        "base_commit": spec["base_commit"],
        **binding,
        "candidate_hash": identity(binding),
        "patch": patch,
        "submitted_patch_hash": digest(patch),
        "provenance": provenance,
        "affected_files": [p for p in spec["allowed_paths"] if files[p] != spec["files"][p]],
        "original": {p: spec["files"][p] for p in spec["allowed_paths"]},
        "modified": {p: files[p] for p in spec["allowed_paths"]},
    }
    return {"id": "patch-" + identity(body), "record_hash": identity(body), **body}


def rebuild(record: dict[str, Any]) -> dict[str, Any]:
    wanted = admit(record["task_id"], record["patch"], record["provenance"])
    if wanted != record:
        raise ValueError("Stored candidate evidence is invalid")
    files = dict(task(record["task_id"])["files"])
    files.update(record["modified"])
    return {**record, "files": files}
