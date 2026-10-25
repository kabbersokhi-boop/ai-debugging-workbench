"""Bounded GitHub HTTPS adapter. No Git checkout, project import, hooks or filters."""

import asyncio
import base64
import gzip
import hashlib
import io
import tarfile
from datetime import UTC, datetime
from typing import Any

import httpx

from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit.contracts import (
    LEGACY_PATH_POLICY,
    MAX_ARCHIVE,
    MAX_EXPANDED,
    MAX_FILE,
    MAX_FILES,
    MAX_SOURCE,
    PATH_POLICY,
    Intake,
    path,
    production,
)


class Rejected(ValueError):
    def __init__(self, status: str, reason: str):
        self.status = status
        super().__init__(reason)


def reject(reason: str):
    raise Rejected("repository_unsupported", reason)


def blob_hash(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git_tree(files: dict[str, bytes], modes: dict[str, str]) -> str:
    nested: dict[str, Any] = {}
    for name, data in files.items():
        current = nested
        parts = name.split("/")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = (modes[name], blob_hash(data))

    def encode(tree):
        content = b""
        for name in sorted(tree, key=lambda n: n + ("/" if isinstance(tree[n], dict) else "")):
            item = tree[name]
            mode, sha = ("40000", encode(item)) if isinstance(item, dict) else item
            content += mode.encode() + b" " + name.encode() + b"\0" + bytes.fromhex(sha)
        return hashlib.sha1(b"tree " + str(len(content)).encode() + b"\0" + content).hexdigest()

    return encode(nested)


def decode_files(snapshot):
    files = {p: base64.b64decode(v, validate=True) for p, v in snapshot["files"].items()}
    validate_files(
        files, snapshot["modes"], snapshot["metadata"].get("path_policy", LEGACY_PATH_POLICY)
    )
    if {p: digest(v) for p, v in files.items()} != snapshot["file_hashes"]:
        raise ValueError("Source file identity mismatch")
    if identity(snapshot["file_hashes"]) != snapshot["source_tree_hash"]:
        raise ValueError("Source tree identity mismatch")
    if git_tree(files, snapshot["modes"]) != snapshot["git_tree"]:
        raise ValueError("Source does not match the Git tree identity")
    body = {k: v for k, v in snapshot.items() if k != "id"}
    if identity(body) != snapshot["id"]:
        raise ValueError("Snapshot identity mismatch")
    return files


def validate_files(files, modes, path_policy=PATH_POLICY):
    if not files or len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_SOURCE:
        reject("Repository file count or total source byte limit exceeded")
    if set(files) != set(modes):
        reject("Missing source file modes")
    for p, data in files.items():
        path(p, path_policy)
        if any("/".join(p.split("/")[:i]) in files for i in range(1, len(p.split("/")))):
            reject("Source file/directory path collision")
        if modes[p] not in ("100644", "100755"):
            reject("Only regular source files are supported; no symlinks or submodules")
        if len(data) > MAX_FILE:
            reject("Repository contains an oversized file")
        if p == ".gitmodules" or data.startswith(b"version https://git-lfs.github.com/spec/v1"):
            reject("Submodules and Git LFS require an unsupported source preparation step")


def snapshot_record(repo, commit, tree, files, modes, metadata):
    validate_files(files, modes, metadata.get("path_policy", LEGACY_PATH_POLICY))
    if git_tree(files, modes) != tree:
        reject("Fetched archive differs from the immutable Git tree (export filters unsupported)")
    hashes = {p: digest(v) for p, v in sorted(files.items())}
    body = {
        "version": "repository-source-v1",
        "repository": repo,
        "base_commit": commit,
        "git_tree": tree,
        "source_tree_hash": identity(hashes),
        "file_hashes": hashes,
        "modes": modes,
        "files": {p: base64.b64encode(v).decode() for p, v in sorted(files.items())},
        "metadata": metadata,
    }
    return {"id": identity(body), **body}


def unpack(data: bytes):
    if len(data) > MAX_ARCHIVE:
        reject("Compressed archive byte limit exceeded")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as zipped:
            expanded = zipped.read(MAX_EXPANDED + 1)
        if len(expanded) > MAX_EXPANDED:
            reject("Expanded archive byte limit exceeded")
        files, modes = {}, {}
        directories = set()
        root = None
        with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
            for count, member in enumerate(archive):
                if count > MAX_FILES * 3:
                    reject("Archive entry limit exceeded")
                name_in_archive = member.name
                if name_in_archive.endswith("/"):
                    if not member.isdir():
                        reject("Trailing slash on a non-directory archive member")
                    name_in_archive = name_in_archive[:-1]
                parts = name_in_archive.split("/", 1)
                if root is None:
                    root = path(parts[0])
                if parts[0] != root:
                    reject("Archive has multiple source roots")
                if len(parts) == 1:
                    if not member.isdir():
                        reject("Invalid archive root")
                    continue
                name = path(parts[1])
                if member.isdir():
                    if name in files or name in directories:
                        reject("Duplicate or colliding archive directory")
                    directories.add(name)
                    continue
                if (
                    not member.isfile()
                    or member.size > MAX_FILE
                    or name in files
                    or name in directories
                ):
                    reject("Special, oversized or duplicate archive member")
                stream = archive.extractfile(member)
                assert stream is not None
                files[name] = stream.read(MAX_FILE + 1)
                modes[name] = "100755" if member.mode & 0o111 else "100644"
                if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_SOURCE:
                    reject("Repository source budget exceeded")
        validate_files(files, modes)
        return files, modes
    except (tarfile.TarError, OSError, EOFError) as error:
        raise Rejected("repository_rejected", "Invalid GitHub source archive") from error


async def bounded_get(client, url: str, limit: int):
    parsed = httpx.URL(url)
    if (
        parsed.scheme != "https"
        or parsed.host not in ("api.github.com", "codeload.github.com")
        or parsed.userinfo
        or parsed.port not in (443, None)
    ):
        raise Rejected("repository_rejected", "Unsafe upstream URL")
    async with client.stream("GET", url, follow_redirects=False) as response:
        if response.is_redirect:
            raise Rejected(
                "repository_rejected", "Upstream redirects are unsupported; use canonical identity"
            )
        if response.status_code != 200:
            raise Rejected(
                "repository_rejected", f"Public GitHub fetch returned HTTP {response.status_code}"
            )
        content = bytearray()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
            if len(content) > limit:
                reject("Upstream response size limit exceeded")
        return bytes(content)


async def fetch(request: Intake, transport=None):
    import json

    repo, sha = request.repository, request.base_commit
    try:
        async with (
            asyncio.timeout(45),
            httpx.AsyncClient(
                timeout=httpx.Timeout(15),
                trust_env=False,
                transport=transport,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Patch-Audit-G1"},
            ) as client,
        ):
            metadata = json.loads(
                await bounded_get(client, f"https://api.github.com/repos/{repo}", 100000)
            )
            if (
                metadata.get("private") is not False
                or metadata.get("full_name", "").lower() != repo
            ):
                raise Rejected(
                    "repository_rejected", "Canonical public repository identity required"
                )
            if metadata.get("size", MAX_SOURCE) > 20000:
                reject("GitHub reported repository size exceeds 20 MB intake limit")
            commit = json.loads(
                await bounded_get(
                    client, f"https://api.github.com/repos/{repo}/commits/{sha}", 1000000
                )
            )
            if commit.get("sha") != sha:
                raise Rejected(
                    "repository_rejected", "GitHub did not resolve the exact immutable commit"
                )
            tree = commit["commit"]["tree"]["sha"]
            listing = json.loads(
                await bounded_get(
                    client,
                    f"https://api.github.com/repos/{repo}/git/trees/{tree}?recursive=1",
                    1000000,
                )
            )
            if listing.get("truncated") or listing.get("sha") != tree:
                reject("Incomplete Git tree listing")
            entries = listing["tree"]
            if len(entries) > MAX_FILES * 3:
                reject("Git tree entry limit exceeded")
            blobs = {}
            for entry in entries:
                name = path(entry["path"])
                if entry["type"] == "tree":
                    continue
                if entry["type"] != "blob" or entry["mode"] not in ("100644", "100755"):
                    reject("Symlinks and submodules are unsupported")
                blobs[name] = entry
            if (
                len(blobs) > MAX_FILES
                or sum(e.get("size", MAX_FILE + 1) for e in blobs.values()) > MAX_SOURCE
            ):
                reject("Git tree source budget exceeded")
            data = await bounded_get(
                client, f"https://codeload.github.com/{repo}/tar.gz/{sha}", MAX_ARCHIVE
            )
            files, modes = await asyncio.to_thread(unpack, data)
            if set(files) != set(blobs) or any(
                blob_hash(v) != blobs[p]["sha"] or modes[p] != blobs[p]["mode"]
                for p, v in files.items()
            ):
                reject("Archive bytes do not match the GitHub commit tree")
            return snapshot_record(
                repo,
                sha,
                tree,
                files,
                modes,
                {
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "adapter": "github-https-archive-v1",
                    "path_policy": PATH_POLICY,
                    "transport": "HTTPS; no redirects; no credentials; 45 second total budget",
                    "archive_sha256": digest(data),
                    "normalization": (
                        "Regular files only; executable bit retained; candidate source read-only"
                    ),
                    "upstream_url": f"https://github.com/{repo}",
                    "license": metadata.get("license"),
                    "attribution_files": [
                        p
                        for p in files
                        if p.rsplit("/", 1)[-1]
                        .lower()
                        .startswith(("license", "copying", "notice", "authors"))
                    ],
                },
            )
    except Rejected:
        raise
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError) as error:
        raise Rejected(
            "repository_rejected", f"Bounded GitHub intake failed: {type(error).__name__}"
        ) from error


def summary(record):
    return {k: v for k, v in record.items() if k != "files"} | {
        "eligible_paths": [p for p in record["files"] if production(p)],
        "source_bytes": sum(len(base64.b64decode(v)) for v in record["files"].values()),
        "file_count": len(record["files"]),
        "license_texts": {
            p: base64.b64decode(record["files"][p]).decode(errors="replace")
            for p in record["metadata"]["attribution_files"]
        },
    }
