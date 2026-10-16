"""Optional guest mode for private staging. Public release uses the separate recorded app.

Opaque 128-bit cookies, persisted ownership and conservative nonrefundable token reservations.
Existing ownerless history is available only in trusted local mode.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from workbench.config import settings
from workbench.db import GuestSession, Investigation, Repair, Run, UsageBucket, sessions


def token_reservation(path: str, method: str) -> int:
    if method != "POST":
        return 0
    if path.endswith("/investigations"):
        return settings.provider_max_requests * (
            settings.model_input_token_limit + settings.model_output_token_limit
        )
    if path.endswith("/repairs"):
        return settings.repair_max_requests * (settings.model_input_token_limit + 2000)
    return 0


async def reserve(owner: UUID, tokens: int) -> None:
    day = datetime.now(UTC).date().isoformat()
    scopes = [
        (f"global:{day}", settings.global_request_limit, settings.global_token_limit),
        (f"session:{owner}", settings.guest_request_limit, settings.guest_token_limit),
    ]
    async with sessions.begin() as session:
        for scope, request_limit, token_limit in scopes:
            await session.execute(
                insert(UsageBucket)
                .values(scope=scope, requests=0, reserved_tokens=0)
                .on_conflict_do_nothing()
            )
            bucket = await session.scalar(
                select(UsageBucket).where(UsageBucket.scope == scope).with_for_update()
            )
            assert bucket is not None
            if bucket.requests >= request_limit or bucket.reserved_tokens + tokens > token_limit:
                raise HTTPException(
                    429, "Session or server admission budget reached. No provider work started."
                )
            bucket.requests += 1
            bucket.reserved_tokens += tokens


async def guest(request: Request) -> tuple[UUID, bool]:
    owner = None
    cookie = request.cookies.get("workbench_guest", "")
    try:
        candidate = UUID(cookie)
        async with sessions() as session:
            row = await session.get(GuestSession, candidate)
            if row and row.expires_at > datetime.now(UTC):
                owner = candidate
    except ValueError:
        pass
    created = owner is None
    if owner is None:
        owner = uuid4()
    await reserve(owner, token_reservation(request.url.path, request.method))
    if created:
        async with sessions.begin() as session:
            session.add(GuestSession(id=owner, expires_at=datetime.now(UTC) + timedelta(hours=24)))
    return owner, created


async def authorize(path: str, owner: UUID) -> None:
    parts = path.split("/")
    if len(parts) < 4 or parts[1] != "api" or parts[2] not in {"runs", "investigations", "repairs"}:
        if path.startswith("/api/snapshots/"):
            snapshot_id = path.rsplit("/", 1)[-1]
            async with sessions() as session:
                found = await session.scalar(
                    select(Investigation.id)
                    .join(Run)
                    .where(Run.owner_id == owner, Investigation.snapshot_id == snapshot_id)
                )
                if found is None:
                    raise HTTPException(404, "Evidence not found in this session")
        return
    kind, value = parts[2:4]
    # Match the protected namespace before validating its identity. A UUID spelling
    # rejected here must never fall through to FastAPI's more permissive parser.
    try:
        resource_id = UUID(value)
    except ValueError:
        raise HTTPException(404, "Run or evidence not found in this session") from None
    if str(resource_id) != value:
        raise HTTPException(404, "Run or evidence not found in this session")
    async with sessions() as session:
        run = await session.get(Run, resource_id) if kind == "runs" else None
        if kind in ("investigations", "repairs"):
            row = await session.get(
                Investigation if kind == "investigations" else Repair, resource_id
            )
            if row:
                run = await session.get(Run, row.run_id)
        if run is None or run.owner_id != owner:
            raise HTTPException(404, "Run or evidence not found in this session")


def check_origin(request: Request) -> None:
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.headers.get("sec-fetch-site") == "cross-site" or request.headers.get(
            "origin"
        ) not in (None, settings.allowed_origin):
            raise HTTPException(403, "Cross-origin actions are not allowed")
        # Browsers send Origin on POST; non-browser clients remain supported on private staging.
