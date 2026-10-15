"""Public release surface: immutable recordings only, no database/provider/executor imports."""

import hashlib
import json
import os
import time
from collections import deque
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = (
    Path(os.environ["RELEASE_ROOT"])
    if "RELEASE_ROOT" in os.environ
    else Path(__file__).resolve().parents[3]
)
RECORDINGS = ROOT / "recordings"
WEB = ROOT / "frontend/dist"
app = FastAPI(
    title="AI debugging workbench · recorded explorer",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
# Single worker, finite global window. There are deliberately zero live execution/token slots.
requests: deque[float] = deque()
guests: dict[str, tuple[float, deque[float]]] = {}


@app.middleware("http")
async def boundary(request: Request, call_next):
    now = time.monotonic()
    while requests and requests[0] < now - 60:
        requests.popleft()
    if len(requests) >= 600:
        return JSONResponse(
            {"detail": "Recorded explorer request limit reached. Retry shortly."},
            429,
            headers={"Retry-After": "60"},
        )
    requests.append(now)
    for key, (expiry, _) in list(guests.items()):
        if expiry < now:
            del guests[key]
    guest_id = request.cookies.get("recorded_guest", "")
    fresh = guest_id not in guests
    if fresh:
        if len(guests) >= 1024:
            return JSONResponse({"detail": "Recorded visitor capacity reached."}, 429)
        guest_id = uuid4().hex
        guests[guest_id] = (now + 900, deque())
    _, window = guests[guest_id]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= 120:
        return JSONResponse({"detail": "Visitor request limit reached. Retry shortly."}, 429)
    window.append(now)
    if request.method not in ("GET", "HEAD"):
        return JSONResponse(
            {"detail": "Recorded mode cannot start inference or execute code."}, 405
        )
    response = await call_next(request)
    if fresh:
        response.set_cookie(
            "recorded_guest",
            guest_id,
            max_age=900,
            httponly=True,
            samesite="strict",
            secure=os.environ.get("RELEASE_SECURE_COOKIES") == "true",
        )
    response.headers.update(
        {
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
                "worker-src 'self' blob:; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        }
    )
    return response


def catalog() -> dict:
    return json.loads((RECORDINGS / "manifest.json").read_text())


@app.get("/api/mode")
async def mode():
    return {
        "mode": "recorded",
        "live_available": False,
        "reason": "Public release serves saved evidence. Live execution remains private.",
    }


@app.get("/api/health")
async def health():
    try:
        manifest = catalog()
        if not manifest["records"] or not (WEB / "index.html").is_file():
            raise ValueError("Missing release bundle")
        for record in manifest["records"]:
            if not (RECORDINGS / record["file"]).is_file():
                raise ValueError("Missing recording")
    except (OSError, ValueError, KeyError):
        raise HTTPException(
            503, "Recorded evidence unavailable; no live fallback is enabled"
        ) from None
    return {
        "status": "ok",
        "mode": "recorded",
        "live_execution_slots": 0,
        "provider_token_budget": 0,
    }


@app.get("/api/recordings")
async def recordings():
    return catalog()


@app.get("/api/recordings/{recording_id}")
async def recording(recording_id: str):
    item = next((r for r in catalog()["records"] if r["id"] == recording_id), None)
    if item is None:
        raise HTTPException(404, "Recording not found")
    data = (RECORDINGS / item["file"]).read_bytes()
    return {"recording_sha256": hashlib.sha256(data).hexdigest(), **json.loads(data)}


@app.get("/api/recorded-assets/{name}")
async def asset(name: str):
    allowed = {"live-repair-before-after.png", "live-repair-checks.png"} | {
        r["comparison_asset"] for r in catalog()["records"] if r.get("comparison_asset")
    }
    if name not in allowed or not (RECORDINGS / name).is_file():
        raise HTTPException(404, "Recorded asset not found")
    return FileResponse(RECORDINGS / name)


@app.get("/recorded/")
async def explorer():
    return FileResponse(WEB / "index.html")


if WEB.is_dir():
    app.mount("/", StaticFiles(directory=WEB, html=True))
