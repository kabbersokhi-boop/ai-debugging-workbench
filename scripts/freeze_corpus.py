"""Freeze only the approved target files from an explicit, immutable Git commit."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from workbench.rag.contracts import Snapshot, SourceFile
from workbench.rag.snapshot import APPROVED_PATHS, identity, validate_snapshot

commit = subprocess.check_output(
    ["git", "rev-parse", "--verify", sys.argv[1] + "^{commit}"], text=True
).strip()
sources = []
digest = hashlib.sha256()
for path in sorted(APPROVED_PATHS):
    content = subprocess.check_output(["git", "show", f"{commit}:{path}"]).decode()
    sources.append(
        SourceFile(
            path=path,
            content=content,
            sha256=hashlib.sha256(content.encode()).hexdigest(),
        )
    )
    digest.update(path.rsplit("/", 1)[1].encode())
    digest.update(b"\0")
    digest.update(content.encode())
snapshot = validate_snapshot(
    Snapshot(
        id=identity(commit, [(s.path, s.sha256) for s in sources]),
        source_commit=commit,
        fixture_sha256=digest.hexdigest(),
        files=sources,
    )
)
target = Path("backend/src/workbench/rag/retail-snapshot.json")
target.write_text(snapshot.model_dump_json(indent=2) + "\n")
print(
    json.dumps(
        {
            "snapshot_id": snapshot.id,
            "source_commit": commit,
            "paths": sorted(APPROVED_PATHS),
        }
    )
)
