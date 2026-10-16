"""Actual API/validator + disposable PostgreSQL; no provider or candidate execution.

Canonical guest paths are supported. Alternate UUID spellings are rejected before
handlers, even when the installed route validator would accept them in local mode.
"""

from uuid import UUID

import httpx
import pytest
import test_rag_integration as fixtures
from fastapi.routing import APIRoute
from pydantic import TypeAdapter

from workbench import access, api, service
from workbench.config import settings
from workbench.db import Investigation, Repair, Run, SourceSnapshot
from workbench.rag.service import InvestigationManager
from workbench.rag.snapshot import load_snapshot
from workbench.repair.service import RepairManager

rag_store = fixtures.rag_store
pytestmark = pytest.mark.integration

# Includes every current UUID-bearing protected route, not just detail endpoints.
ENDPOINTS = [
    ("GET", "/api/runs/{run_id}", None),
    ("POST", "/api/runs/{run_id}/cancel", None),
    ("GET", "/api/runs/{run_id}/artifacts/{name}", None),
    ("POST", "/api/runs/{run_id}/investigations", {"report": "Offline access regression"}),
    ("GET", "/api/runs/{run_id}/investigations", None),
    ("GET", "/api/investigations/{investigation_id}", None),
    ("POST", "/api/investigations/{investigation_id}/cancel", None),
    ("POST", "/api/investigations/{investigation_id}/repairs", None),
    ("GET", "/api/investigations/{investigation_id}/repairs", None),
    ("GET", "/api/repairs/{repair_id}", None),
    ("POST", "/api/repairs/{repair_id}/cancel", None),
    ("GET", "/api/repairs/{repair_id}/attempts/{attempt}/patch", None),
    ("GET", "/api/repairs/{repair_id}/evidence", None),
    ("POST", "/api/repairs/{repair_id}/attempts/{attempt}/preview", None),
    ("POST", "/api/repairs/{repair_id}/attempts/{attempt}/remote", {"action": "reset"}),
    ("GET", "/api/repairs/{repair_id}/attempts/{attempt}/screenshot", None),
]


def spellings(value: UUID) -> dict[str, str]:
    text = str(value)
    mixed = "".join(c.upper() if i % 2 else c for i, c in enumerate(text))
    return {
        "canonical": text,
        "uppercase": text.upper(),
        "mixed-case": mixed,
        "hyphenless": value.hex,
        "uppercase-hyphenless": value.hex.upper(),
        "braces": "{" + text + "}",
        "uppercase-braces": "{" + text.upper() + "}",
        "urn": value.urn,
        "urn-uppercase-hex": "urn:uuid:" + text.upper(),
        "braced-hyphenless": "{" + value.hex + "}",
        "uppercase-urn-prefix": value.urn.upper(),
        "urn-hyphenless": "urn:uuid:" + value.hex,
        "extra-hyphens": text.replace("-", "--"),
        "whitespace": " " + text + " ",
        "unicode-hyphens": text.replace("-", "\u2010"),
        "malformed": "not-a-uuid",
    }


async def test_guest_uuid_spellings_cannot_bypass_any_resource_handler(
    rag_store, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "guest_access", True)
    # Exercise ownership rather than hitting reservation ceilings during the matrix.
    # Separate tests retain the normal quota/expiry/idempotency assertions.
    for name in ("guest_token_limit", "global_token_limit"):
        monkeypatch.setattr(settings, name, 1_000_000_000)
    for module in (access, api, service):
        monkeypatch.setattr(module, "sessions", rag_store)
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)
    monkeypatch.setattr(settings, "repair_broker_url", "http://offline-broker.invalid")
    ids = {
        "run_id": UUID("aabbccdd-1122-4a5b-8c9d-aabbccddeeff"),
        "investigation_id": UUID("bbcceedd-1122-4a5b-8c9d-aabbccddeeff"),
        "repair_id": UUID("ccddeeff-1122-4a5b-8c9d-aabbccddeeff"),
    }
    other_run = UUID("ddeeffaa-1122-4a5b-8c9d-aabbccddeeff")
    snapshot = load_snapshot()
    candidate_hash = "a" * 64
    inv = InvestigationManager(store=rag_store)
    repairs = RepairManager(store=rag_store)
    monkeypatch.setattr(api.app.state, "investigations", inv, raising=False)
    monkeypatch.setattr(api.app.state, "repairs", repairs, raising=False)
    effects = []

    # Keep the actual get/history/serialization handlers. Only effectful coordinator
    # operations and broker I/O are deterministic boundary fixtures.
    async def run_cancel(run_id):
        effects.append("run.cancel")
        return await service.get_run(run_id)

    class RunActions:
        cancel = staticmethod(run_cancel)

    monkeypatch.setattr(api.app.state, "manager", RunActions(), raising=False)

    async def investigation_action(*args):
        effects.append("investigation.action")
        return await inv.get(ids["investigation_id"])

    async def repair_action(*args):
        effects.append("repair.action")
        return await repairs.get(ids["repair_id"])

    async def broker(*args):
        effects.append("broker.preview")
        return {"candidate_hash": candidate_hash}

    for name in ("create", "cancel"):
        monkeypatch.setattr(inv, name, investigation_action)
        monkeypatch.setattr(repairs, name, repair_action)
    monkeypatch.setattr(repairs, "broker", broker)
    original_send = httpx.AsyncClient.send

    async def send(client, request, **kwargs):
        if request.url.host == "offline-broker.invalid":
            effects.append("broker.http")
            if request.method == "GET":
                return httpx.Response(200, content=b"OFFLINE_PRIVATE_SCREENSHOT", request=request)
            return httpx.Response(200, json={"candidate_hash": candidate_hash}, request=request)
        return await original_send(client, request, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    entered = []

    def observe(call, path):
        async def endpoint(**kwargs):
            entered.append(path)
            return await call(**kwargs)

        return endpoint

    routes = [
        r
        for r in api.app.routes
        if isinstance(r, APIRoute)
        and r.path.startswith(("/api/runs/", "/api/investigations/", "/api/repairs/"))
    ]
    assert {(m, r.path) for r in routes for m in (r.methods or ())} == {
        (method, path) for method, path, _ in ENDPOINTS
    }
    for route in routes:
        monkeypatch.setattr(route.dependant, "call", observe(route.dependant.call, route.path))

    transport = httpx.ASGITransport(app=api.app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://private") as a,
        httpx.AsyncClient(transport=transport, base_url="http://private") as b,
    ):
        await a.get("/api/mode")
        await b.get("/api/mode")
        owners = [UUID(c.cookies["workbench_guest"]) for c in (a, b)]
        assert owners[0] != owners[1]
        async with rag_store.begin() as session:
            session.add_all(
                [
                    Run(
                        id=ids["run_id"],
                        owner_id=owners[0],
                        bug_id="cart-quantity",
                        status="cancelled",
                    ),
                    Run(
                        id=other_run, owner_id=owners[1], bug_id="cart-quantity", status="cancelled"
                    ),
                    SourceSnapshot(
                        id=snapshot.id,
                        source_commit=snapshot.source_commit,
                        fixture_sha256=snapshot.fixture_sha256,
                        manifest=snapshot.model_dump(),
                    ),
                ]
            )
            await session.flush()
            session.add(
                Investigation(
                    id=ids["investigation_id"],
                    run_id=ids["run_id"],
                    status="completed",
                    report="OFFLINE_PRIVATE_REPORT",
                    snapshot_id=snapshot.id,
                    events=[],
                    provider_calls=[],
                )
            )
            await session.flush()
            session.add(
                Repair(
                    id=ids["repair_id"],
                    run_id=ids["run_id"],
                    investigation_id=ids["investigation_id"],
                    snapshot_id=snapshot.id,
                    status="cancelled",
                    events=[],
                    state={
                        "attempts": [
                            {
                                "number": 1,
                                "candidate": {
                                    "diff": "OFFLINE_PRIVATE_PATCH",
                                    "candidate_hash": candidate_hash,
                                },
                                "verification": {
                                    "artifact_id": "b" * 64,
                                    "verifier_version": "offline",
                                },
                            }
                        ]
                    },
                )
            )
        folder = tmp_path / str(ids["run_id"])
        folder.mkdir()
        (folder / "before.png").write_bytes(b"OFFLINE_PRIVATE_PIXELS")
        for client, expected in ((a, ids["run_id"]), (b, other_run)):
            assert [r["id"] for r in (await client.get("/api/runs")).json()] == [str(expected)]
        assert (await a.get(f"/api/snapshots/{snapshot.id}")).status_code == 200
        assert (await b.get(f"/api/snapshots/{snapshot.id}")).status_code == 404

        validator = TypeAdapter(UUID)
        for spelling in spellings(ids["run_id"]):
            values = {key: spellings(value)[spelling] for key, value in ids.items()}
            canonical = spelling == "canonical"
            try:
                validator.validate_python(values["run_id"])
                accepted = True
            except ValueError:
                accepted = False
            # Probe the actual installed route validator in trusted local mode.
            monkeypatch.setattr(settings, "guest_access", False)
            for kind, key in (
                ("runs", "run_id"),
                ("investigations", "investigation_id"),
                ("repairs", "repair_id"),
            ):
                response = await b.get(f"/api/{kind}/{values[key]}")
                assert response.status_code == (200 if accepted else 422), (spelling, response.text)
            monkeypatch.setattr(settings, "guest_access", True)
            for method, template, payload in ENDPOINTS:
                path = template.format(**values, name="before.png", attempt=1)
                entered.clear()
                effects.clear()
                response = await b.request(method, path, json=payload)
                assert response.status_code == 404, (spelling, method, path, response.text)
                assert response.json() == {"detail": "Run or evidence not found in this session"}
                assert not entered and not effects, (spelling, path, entered, effects)
                response = await a.request(method, path, json=payload)
                assert response.status_code == (
                    202
                    if canonical
                    and template.endswith(("/investigations", "/repairs"))
                    and method == "POST"
                    else 200
                    if canonical
                    else 404
                ), (spelling, method, path, response.text)
                assert bool(entered) == canonical
                if not canonical:
                    assert not effects
        # No action fixture changed persisted records; forbidden requests never
        # entered a handler, including provider admission and candidate controls.
        assert (await inv.get(ids["investigation_id"]))["status"] == "completed"
        assert (await repairs.get(ids["repair_id"]))["status"] == "cancelled"
