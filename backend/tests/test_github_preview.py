"""PR convenience never confers source admission, approval or public execution authority."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from workbench.config import settings
from workbench.release import app as recorded
from workbench.repository_audit.github_preview import Preview, preview
from workbench.repository_audit.intake import Rejected
from workbench.repository_audit.routes import router

URL = "https://github.com/owner/project/pull/12"


def metadata():
    repo = {"full_name": "owner/project", "private": False}
    pr = {
        "number": 12,
        "title": "Fix behavior",
        "base": {"repo": repo, "sha": "a" * 40},
        "head": {"repo": repo, "sha": "b" * 40},
        "changed_files": 2,
        "additions": 4,
        "deletions": 1,
    }
    return repo, pr


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/owner/project/pull/12",
        "https://github.com.evil/owner/project/pull/12",
        "https://user:secret@github.com/owner/project/pull/12",
        "https://github.com:443/owner/project/pull/12",
        "https://github.com/owner/project/pull/12?url=http://127.0.0.1",
        "https://github.com/owner/project/pull/12#x",
        "https://github.com/owner/project/pull/12/",
        "https://github.com/owner/project.git/pull/12",
        "https://github.com/owner/../pull/12",
        "https://github.com/owner/project/pull/0",
        "https://github.com/owner/project/pull/01",
        "https://github.com/owner%2fprivate/project/pull/12",
        "http://127.0.0.1:8010/",
        "git@github.com:owner/project/pull/12",
    ],
)
async def test_preview_rejects_noncanonical_destinations_without_network(url):
    def network(request):
        pytest.fail("Invalid input reached network")

    with pytest.raises(Rejected):
        await preview(Preview(url=url), httpx.MockTransport(network))


async def test_preview_is_fixed_host_unauthenticated_metadata_and_never_an_admission():
    repo, pr = metadata()
    paths = []

    def network(request):
        assert request.url.scheme == "https" and request.url.host == "api.github.com"
        assert "authorization" not in request.headers and "cookie" not in request.headers
        paths.append(request.url.path)
        return httpx.Response(200, json=pr if request.url.path.endswith("pulls/12") else repo)

    value = await preview(Preview(url=URL), httpx.MockTransport(network))
    assert paths == ["/repos/owner/project", "/repos/owner/project/pulls/12"]
    assert value["base_commit"] == "a" * 40 and value["head_commit"] == "b" * 40
    assert value["admission"] == "not_admitted" and value["execution_authorized"] is False
    assert not any(k in value for k in ("candidate_id", "snapshot_id", "plan_id", "patch"))
    assert "merge-base" in value["limitation"]


@pytest.mark.parametrize(
    "failure",
    [
        "private",
        "identity",
        "head",
        "sha",
        "number",
        "counts",
        "json",
        "redirect",
        "404",
        "429",
        "oversize",
        "connection",
        "slow",
    ],
)
async def test_preview_rejects_untrusted_or_unavailable_metadata(failure, monkeypatch):
    import workbench.repository_audit.github_preview as module

    repo, pr = metadata()
    if failure == "private":
        repo["private"] = True
    if failure == "identity":
        repo["full_name"] = "different/project"
    if failure == "head":
        pr["head"]["repo"] = None
    if failure == "sha":
        pr["head"]["sha"] = "main"
    if failure == "number":
        pr["number"] = 13
    if failure == "counts":
        pr["additions"] = True
    if failure == "slow":
        original = module.anyio.fail_after
        monkeypatch.setattr(module.anyio, "fail_after", lambda seconds: original(0.02))

    async def network(request):
        if failure == "slow":
            await asyncio.sleep(10)
        if failure == "connection":
            raise httpx.ConnectError("private upstream detail")
        if failure == "json":
            return httpx.Response(200, text="<html>invalid</html>")
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "http://localhost"})
        if failure in ("404", "429"):
            return httpx.Response(int(failure))
        if failure == "oversize":
            return httpx.Response(200, content=b" " * 100_001)
        return httpx.Response(200, json=pr if request.url.path.endswith("pulls/12") else repo)

    with pytest.raises(Rejected) as error:
        await preview(Preview(url=URL), httpx.MockTransport(network))
    assert error.value.status == "preview_unavailable"
    assert "private upstream detail" not in str(error.value)


async def test_preview_keeps_local_owner_gate_and_is_absent_from_recorded_app(monkeypatch):
    monkeypatch.setattr(settings, "guest_access", True)
    local = FastAPI()
    local.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=local), base_url="http://local"
    ) as client:
        assert (
            await client.post("/api/repository-audits/github-preview", json={"url": URL})
        ).status_code == 403
    assert not any(
        getattr(r, "path", "").startswith("/api/repository-audits") for r in recorded.routes
    )
