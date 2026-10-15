import hashlib
import json
import re
from importlib.resources import files

import tree_sitter_javascript
from tree_sitter import Language, Parser

from workbench.rag.contracts import ContextChunk, Snapshot

APPROVED_PATHS = frozenset(
    f"fixtures/retail/{name}" for name in ("cart.js", "index.html", "styles.css", "README.md")
)
CHUNKER_VERSION = "source-boundaries-v1"


def identity(source_commit: str, file_hashes: list[tuple[str, str]]) -> str:
    return hashlib.sha256(json.dumps([source_commit, sorted(file_hashes)]).encode()).hexdigest()


def validate_snapshot(snapshot: Snapshot) -> Snapshot:
    paths = [source.path for source in snapshot.files]
    if set(paths) != APPROVED_PATHS or len(paths) != len(APPROVED_PATHS):
        raise ValueError("Snapshot must contain exactly the approved target source paths")
    if not re.fullmatch(r"[0-9a-f]{40}", snapshot.source_commit):
        raise ValueError("Snapshot requires an immutable Git commit")
    digest = hashlib.sha256()
    for source in sorted(snapshot.files, key=lambda source: source.path):
        if source.origin_path is not None and (
            source.path != "fixtures/retail/cart.js"
            or not re.fullmatch(r"fixtures/scenarios/[a-z-]+/cart\.js", source.origin_path)
        ):
            raise ValueError("Invalid source provenance path")
        if hashlib.sha256(source.content.encode()).hexdigest() != source.sha256:
            raise ValueError("Snapshot content hash mismatch")
        digest.update(source.path.rsplit("/", 1)[1].encode())
        digest.update(b"\0")
        digest.update(source.content.encode())
    if digest.hexdigest() != snapshot.fixture_sha256:
        raise ValueError("Fixture/source manifest mismatch")
    if snapshot.id != identity(
        snapshot.source_commit, [(s.path, s.sha256) for s in snapshot.files]
    ):
        raise ValueError("Snapshot identity mismatch")
    return snapshot


def load_snapshot(snapshot_id: str | None = None) -> Snapshot:
    package = files("workbench.rag")
    original = validate_snapshot(
        Snapshot.model_validate_json(package.joinpath("retail-snapshot.json").read_text())
    )
    if snapshot_id is None or snapshot_id == original.id:
        return original
    if not re.fullmatch(r"[a-f0-9]{64}", snapshot_id):
        raise ValueError("Invalid snapshot identity")
    allowed = {c["snapshot_id"] for c in scenario_manifest()["cases"]}
    if snapshot_id not in allowed:
        raise ValueError("Snapshot is not an approved scenario")
    snapshot = validate_snapshot(
        Snapshot.model_validate_json(package.joinpath(f"scenarios/{snapshot_id}.json").read_text())
    )
    if snapshot.id != snapshot_id:
        raise ValueError("Packaged snapshot identity mismatch")
    return snapshot


def scenario_manifest() -> dict:
    return json.loads(files("workbench.rag").joinpath("scenarios.json").read_text())


def scenario(scenario_id: str) -> dict:
    for case in scenario_manifest()["cases"]:
        if case["id"] == scenario_id:
            return case
    raise ValueError("Unknown approved scenario")


def snapshot_scenario(snapshot_id: str) -> dict:
    for case in scenario_manifest()["cases"]:
        if case["snapshot_id"] == snapshot_id:
            return case
    raise ValueError("Snapshot has no approved scenario")


def chunk_snapshot(snapshot: Snapshot) -> list[ContextChunk]:
    validate_snapshot(snapshot)
    chunks: list[ContextChunk] = []
    parser = Parser(Language(tree_sitter_javascript.language()))
    for source in snapshot.files:
        lines = source.content.splitlines()
        boundaries: list[tuple[int, int, str]] = []
        if source.path.endswith(".js"):
            tree = parser.parse(source.content.encode())
            if tree.root_node.has_error:
                raise ValueError("Invalid JavaScript in approved snapshot")
            for node in tree.root_node.named_children:
                symbol = node.child_by_field_name("name")
                name = symbol.text.decode() if symbol and symbol.text else node.type
                boundaries.append((node.start_point.row, node.end_point.row + 1, name))
        elif source.path.endswith(".md"):
            starts = [i for i, line in enumerate(lines) if line.startswith("#")]
            for i, start in enumerate(starts):
                boundaries.append(
                    (start, starts[i + 1] if i + 1 < len(starts) else len(lines), lines[start])
                )
        else:
            # HTML sections and CSS rules remain line-grounded; cap long sections below.
            starts = [0] + [
                i
                for i, line in enumerate(lines)
                if i > 0
                and (
                    (
                        source.path.endswith(".css")
                        and line
                        and not line[0].isspace()
                        and "{" in line
                    )
                    or (
                        source.path.endswith(".html")
                        and re.match(r"\s*<(section|header|footer|main)\b", line)
                    )
                )
            ]
            for i, start in enumerate(starts):
                boundaries.append(
                    (
                        start,
                        starts[i + 1] if i + 1 < len(starts) else len(lines),
                        lines[start].strip()[:80],
                    )
                )
        for start, end, symbol in boundaries:
            # Preserve complete useful boundaries when small; split large blocks at line boundaries.
            cursor = start
            while cursor < end:
                stop = cursor
                cost = 0
                while stop < end and stop - cursor < 36:
                    line_cost = len(lines[stop].encode()) + 1
                    if cost + line_cost > 1500 and stop > cursor:
                        break
                    cost += line_cost
                    stop += 1
                content = "\n".join(lines[cursor:stop])
                if content.strip():
                    key = f"{snapshot.id}:{source.path}:{cursor}:{stop}:{content}"
                    chunks.append(
                        ContextChunk(
                            source_id=hashlib.sha256(key.encode()).hexdigest()[:16],
                            path=source.path,
                            start_line=cursor + 1,
                            end_line=stop,
                            symbol=symbol,
                            content=content,
                        )
                    )
                cursor = stop
    if len({chunk.source_id for chunk in chunks}) != len(chunks):
        raise ValueError("Source identifier collision")
    return chunks
