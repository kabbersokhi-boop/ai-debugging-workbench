"""Exact production-only patch admission using the accepted dual-parser implementation."""

from workbench.evaluator.catalog import digest, identity
from workbench.patch_audit.admission import apply_patch
from workbench.repository_audit.contracts import MAX_SOURCE, Import, Plan, production
from workbench.repository_audit.intake import decode_files


def admit(snapshot, request: Import):
    files = decode_files(snapshot)
    scope = request.approved_paths
    if len(scope) != len(set(scope)) or any(p not in files or not production(p) for p in scope):
        raise ValueError(
            "Patch rejected: approve up to four existing production files; "
            "tests/configuration/setup unsupported"
        )
    try:
        selected = {p: files[p].decode("utf-8") for p in scope}
    except UnicodeDecodeError as error:
        raise ValueError("Patch rejected: changed files must be UTF-8 text") from error
    changed = apply_patch({"files": selected, "allowed_paths": scope}, request.patch)
    files.update({p: value.encode() for p, value in changed.items()})
    if sum(map(len, files.values())) > MAX_SOURCE:
        raise ValueError("Patch rejected: applied-source byte limit exceeded")
    affected = [p for p in scope if selected[p] != changed[p]]
    if not affected:
        raise ValueError("Patch rejected: no production changes")
    binding = {
        "repository": snapshot["repository"],
        "base_commit": snapshot["base_commit"],
        "source_tree_hash": snapshot["source_tree_hash"],
        "applied_source_hashes": {p: digest(v) for p, v in sorted(files.items())},
    }
    body = {
        "version": "repository-candidate-v1",
        "snapshot_id": snapshot["id"],
        **binding,
        "candidate_hash": identity(binding),
        "patch": request.patch,
        "submitted_patch_hash": digest(request.patch),
        "approved_paths": scope,
        "affected_files": affected,
        "original": {p: selected[p] for p in affected},
        "modified": {p: changed[p] for p in affected},
        "provenance": {
            "category": "user_declared",
            "author_label": request.author_label,
            "source_reference": request.source_reference,
            "limitations": "Imported authorship is user-declared and unverified.",
        },
    }
    return {"id": identity(body), **body}


def rebuild(snapshot, candidate):
    wanted = admit(
        snapshot,
        Import(
            snapshot_id=snapshot["id"],
            patch=candidate["patch"],
            approved_paths=candidate["approved_paths"],
            author_label=candidate["provenance"]["author_label"],
            source_reference=candidate["provenance"]["source_reference"],
        ),
    )
    if wanted != candidate:
        raise ValueError("Candidate evidence does not match the source and patch")
    files = decode_files(snapshot)
    files.update({p: v.encode() for p, v in candidate["modified"].items()})
    return files


def check_plan(snapshot, candidate, value):
    plan = Plan.model_validate(value)
    if plan.snapshot_id != snapshot["id"] or plan.candidate_hash != candidate["candidate_hash"]:
        raise ValueError("Execution plan belongs to another source or candidate")
    if plan.working_directory != "." and not any(
        p.startswith(plan.working_directory + "/") for p in snapshot["files"]
    ):
        raise ValueError("Execution working directory does not exist")
    from workbench.repository_audit.contracts import POLICY

    if plan.policy_hash != identity(POLICY):
        raise ValueError("Execution plan uses an unsupported sandbox policy")
    return plan
