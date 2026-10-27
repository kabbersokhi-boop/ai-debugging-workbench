"""Local, display-only public PR metadata. Never admits source, patches or execution."""

import json
import re
from datetime import UTC, datetime

import anyio
import httpx
from pydantic import Field

from workbench.repository_audit.contracts import Contract, repository
from workbench.repository_audit.intake import Rejected, bounded_get

URL = re.compile(r"https://github\.com/([^/]+)/([^/]+)/pull/([1-9][0-9]{0,8})\Z")
SHA = re.compile(r"[a-f0-9]{40}\Z")


class Preview(Contract):
    url: str = Field(max_length=240)


async def preview(payload: Preview, transport=None):
    match = URL.fullmatch(payload.url)
    if not match:
        raise Rejected("preview_unsupported", "Use https://github.com/owner/repository/pull/123")
    try:
        repo = repository(f"{match[1]}/{match[2]}")
    except ValueError:
        raise Rejected("preview_unsupported", "Canonical public repository required") from None
    number = int(match[3])
    try:
        with anyio.fail_after(12):
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5),
                trust_env=False,
                follow_redirects=False,
                transport=transport,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Patch-Audit"},
            ) as client:
                metadata = json.loads(
                    await bounded_get(client, f"https://api.github.com/repos/{repo}", 100_000)
                )
                if metadata["private"] is not False or metadata["full_name"].lower() != repo:
                    raise ValueError("Public identity mismatch")
                pr = json.loads(
                    await bounded_get(
                        client, f"https://api.github.com/repos/{repo}/pulls/{number}", 300_000
                    )
                )
                if (
                    type(pr["number"]) is not int
                    or pr["number"] != number
                    or pr["base"]["repo"]["full_name"].lower() != repo
                    or pr["base"]["repo"]["private"] is not False
                    or pr["head"]["repo"]["private"] is not False
                ):
                    raise ValueError("PR identity mismatch or deleted/private head")
                base, head = pr["base"]["sha"], pr["head"]["sha"]
                if not SHA.fullmatch(base) or not SHA.fullmatch(head):
                    raise ValueError("Immutable revisions required")
                counts = {key: pr[key] for key in ("changed_files", "additions", "deletions")}
                if any(type(v) is not int or v < 0 for v in counts.values()):
                    raise ValueError("Invalid change counts")
                if not isinstance(pr["title"], str) or len(pr["title"]) > 1000:
                    raise ValueError("Invalid title")
                return {
                    "version": "github-pr-preview-v1",
                    "url": f"https://github.com/{repo}/pull/{number}",
                    "repository": repo,
                    "number": number,
                    "title": pr["title"],
                    "base_commit": base,
                    "head_commit": head,
                    "head_repository": repository(pr["head"]["repo"]["full_name"]),
                    "observed_at": datetime.now(UTC).isoformat(),
                    **counts,
                    "admission": "not_admitted",
                    "execution_authorized": False,
                    "limitation": (
                        "Metadata preview only. No source or candidate admitted. "
                        "The PR can change; "
                        "these are observed commit IDs, not recomputed source/patch identities. "
                        "The base tip may differ from the patch merge-base. Use manual immutable "
                        "source and production-only patch admission; tests/configuration changes, "
                        "new/deleted files and unsupported environments remain rejected."
                    ),
                }
    except (
        Rejected,
        httpx.HTTPError,
        TimeoutError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ):
        raise Rejected(
            "preview_unavailable",
            "Public PR metadata unavailable or invalid. Private/deleted repositories, rate limits "
            "and slow upstream responses are unsupported. No source admitted; use manual intake.",
        ) from None
