"""Fixed browser recipes, served separately from the database/API process.

This runner executes trusted reproduction code only. It is not a generated-code sandbox.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import anyio
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import Browser, Page, async_playwright

from workbench.config import settings
from workbench.contracts import Artifact, Check, Observation, ReproductionResult, RunnerEvent
from workbench.rag.snapshot import load_snapshot, scenario
from workbench.repair.verifier import verify

logger = logging.getLogger(__name__)
PROCEDURE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
slots = asyncio.Semaphore(settings.max_active_runs)
active_ids: set[UUID] = set()


def fixture_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.iterdir()):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


async def observe(page: Page) -> Observation:
    async def cents(name: str) -> int:
        value = await page.get_by_test_id(name).get_attribute("data-cents")
        if value is None:
            raise ValueError(f"Missing monetary evidence: {name}")
        return int(value)

    return Observation(
        quantity=int(await page.get_by_role("spinbutton", name="Quantity").input_value()),
        unit_price_cents=await cents("unit-price"),
        line_total_cents=await cents("line-total"),
        subtotal_cents=await cents("subtotal"),
        shipping_cents=await cents("shipping"),
        total_cents=await cents("total"),
    )


def validate_baseline(baseline: Observation) -> None:
    if baseline.model_dump() != {
        "quantity": 1,
        "unit_price_cents": 6400,
        "line_total_cents": 6400,
        "subtotal_cents": 6400,
        "shipping_cents": 800,
        "total_cents": 7200,
    }:
        raise ValueError("Baseline contract failed; cannot attribute the reported quantity defect.")


def evaluate(baseline: Observation, observed: Observation) -> list[Check]:
    """Trusted expectations independent of the fixture's calculation implementation."""
    validate_baseline(baseline)
    if observed.quantity != 3:
        raise ValueError("Browser action did not set quantity to three.")
    expected = {
        "Line amount": (19200, observed.line_total_cents),
        "Subtotal": (19200, observed.subtotal_cents),
        "Shipping": (0, observed.shipping_cents),
        "Order total": (19200, observed.total_cents),
    }
    return [
        Check(name=name, expected_cents=want, observed_cents=got, passed=want == got)
        for name, (want, got) in expected.items()
    ]


def event(
    kind: Literal["step", "screenshot", "result", "error"],
    title: str,
    detail: str,
    **data: Any,
) -> bytes:
    return (
        RunnerEvent(kind=kind, title=title, detail=detail, data=data).model_dump_json() + "\n"
    ).encode()


async def reproduce(run_id: UUID) -> AsyncIterator[bytes]:
    started = time.monotonic()
    folder = settings.artifact_dir / str(run_id)
    folder.mkdir(parents=True, exist_ok=False)
    logs: list[dict[str, str]] = []
    async with slots, browser_session() as browser:
        context = await browser.new_context(
            viewport={"width": 1200, "height": 820},
            device_scale_factor=1,
            locale="en-US",
            timezone_id="UTC",
            service_workers="block",
        )
        # Prevent fixture scripts from contacting arbitrary services or metadata endpoints.
        await context.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith("http://127.0.0.1:8011/retail/")
                else route.abort()
            ),
        )
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = await context.new_page()
        page.set_default_timeout(8000)
        page.on(
            "console", lambda message: logs.append({"type": message.type, "text": message.text})
        )
        page.on("pageerror", lambda error: logs.append({"type": "error", "text": str(error)}))
        yield event(
            "step",
            "Fresh browser ready",
            "Chromium started with an empty, isolated browser context.",
            browser_version=browser.version,
        )
        response = await page.goto("http://127.0.0.1:8011/retail/", wait_until="networkidle")
        if response is None or response.status != 200:
            raise ValueError("Retail fixture did not return HTTP 200.")
        yield event(
            "step",
            "Storefront opened",
            "Loaded the local Fieldwork Supply fixture. External browser requests are blocked.",
        )
        await page.get_by_role("button", name="Add to bag").click()
        baseline = await observe(page)
        # Validate baseline before labeling its screenshot as a passing control.
        validate_baseline(baseline)
        await page.screenshot(path=folder / "before.png", full_page=True)
        yield event(
            "screenshot",
            "Baseline confirmed",
            "One daypack: $64 subtotal + $8 shipping = $72. Baseline pricing contract passed.",
            artifact="before.png",
            observation=baseline.model_dump(),
        )
        await page.get_by_role("button", name="Increase quantity").click(click_count=2)
        observed = await observe(page)
        checks = evaluate(baseline, observed)
        await page.screenshot(path=folder / "after.png", full_page=True)
        yield event(
            "screenshot",
            "Quantity changed to three",
            "Captured the browser after two clicks on Increase quantity.",
            artifact="after.png",
            observation=observed.model_dump(),
        )
        if all(check.passed for check in checks):
            status = "not_reproduced"
        elif (
            observed.line_total_cents,
            observed.subtotal_cents,
            observed.shipping_cents,
            observed.total_cents,
        ) == (19200, 6400, 800, 7200):
            status = "reproduced"
        else:
            raise ValueError(
                "Unexpected pricing mismatch; the reported defect signature was not confirmed."
            )
        await context.tracing.stop(path=folder / "trace.zip")
        await context.close()
        (folder / "console.json").write_text(json.dumps(logs, indent=2))
        result = ReproductionResult(
            status=status,
            checks=checks,
            baseline=baseline,
            observed=observed,
            artifacts=[
                Artifact(name="before.png", label="Baseline screenshot", media_type="image/png"),
                Artifact(name="after.png", label="Defect screenshot", media_type="image/png"),
                Artifact(name="trace.zip", label="Playwright trace", media_type="application/zip"),
                Artifact(
                    name="console.json", label="Browser console", media_type="application/json"
                ),
                Artifact(
                    name="result.json",
                    label="Reproduction result",
                    media_type="application/json",
                ),
            ],
            fixture_sha256=fixture_digest(settings.fixture_dir),
            source_snapshot=load_snapshot().id,
            runtime_identity={
                "procedure_sha256": PROCEDURE_SHA256,
                "chromium": browser.version,
            },
            browser_version=browser.version,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        (folder / "result.json").write_text(result.model_dump_json(indent=2))
        yield event(
            "result",
            "Defect reproduced" if status == "reproduced" else "Defect not reproduced",
            f"{sum(not c.passed for c in checks)} of {len(checks)} pricing assertions failed. "
            "This is reproduction evidence; no patch has been generated or verified.",
            result=result.model_dump(),
        )


async def reproduce_scenario(run_id: UUID, scenario_id: str) -> AsyncIterator[bytes]:
    case = scenario(scenario_id)
    snapshot = load_snapshot(case["snapshot_id"])
    started = time.monotonic()
    folder = settings.artifact_dir / str(run_id)
    folder.mkdir(parents=True, exist_ok=False)
    yield event(
        "step",
        "Scenario source bound",
        f"Approved scenario {scenario_id}; frozen source {snapshot.id}.",
    )
    async with slots, browser_session() as browser:
        result = await verify(
            browser,
            snapshot.fixture_sha256,
            folder / "after.png",
            f"http://127.0.0.1:8011/scenarios/{scenario_id}/retail/",
            folder / "before.png",
            issue_name=case["issue_check"],
        )
    issue = next(c for c in result["checks"] if c["name"] == case["issue_check"])
    status = "not_reproduced" if issue["passed"] else "reproduced"

    def cents(value):
        return round(float(value.replace("$", "").replace(",", "")) * 100)

    def observed(check):
        values = check["observed"]
        return Observation(
            quantity=int(check["controls"]["quantity"]),
            unit_price_cents=6400,
            line_total_cents=cents(values["line-total"]),
            subtotal_cents=cents(values["subtotal"]),
            shipping_cents=cents(values["shipping"]),
            total_cents=cents(values["total"]),
        )

    baseline = next(c for c in result["checks"] if c["name"] == "add-one-baseline")
    checks = [
        Check(
            name=k,
            expected_cents=cents(issue["expected"][k]),
            observed_cents=cents(issue["observed"][k]),
            passed=issue["expected"][k] == issue["observed"][k],
        )
        for k in ("line-total", "subtotal", "shipping", "total")
    ]
    for name, label in [
        ("before.png", "One-item control capture"),
        ("after.png", "Reported scenario action capture"),
    ]:
        yield event(
            "screenshot",
            label,
            "Captured during the versioned trusted browser procedure.",
            artifact=name,
        )
    (folder / "console.json").write_text(json.dumps(result["page_errors"]))
    reproduction = ReproductionResult(
        status=status,
        checks=checks,
        baseline=observed(baseline),
        observed=observed(issue),
        source_snapshot=snapshot.id,
        runtime_identity={
            "procedure_sha256": PROCEDURE_SHA256,
            "chromium": result["browser_version"],
        },
        behavioral_checks=result["checks"],
        fixture_sha256=snapshot.fixture_sha256,
        browser_version=result["browser_version"],
        duration_ms=round((time.monotonic() - started) * 1000),
        artifacts=[
            Artifact(
                name=n,
                label=n,
                media_type="image/png" if n.endswith(".png") else "application/json",
            )
            for n in ("before.png", "after.png", "result.json", "console.json")
        ],
    )
    (folder / "result.json").write_text(reproduction.model_dump_json(indent=2))
    yield event(
        "result",
        "Defect reproduced" if status == "reproduced" else "Defect not reproduced",
        f"Issue check {case['issue_check']}: {'passed' if issue['passed'] else 'failed'}. "
        "No repair is inferred.",
        result=reproduction.model_dump(),
    )


def scenario_resource(scenario_id: str, name: str) -> Response:
    try:
        case = scenario(scenario_id)
    except ValueError:
        raise HTTPException(404, "Unknown approved scenario") from None
    if name not in ("", "index.html", "cart.js", "styles.css"):
        raise HTTPException(404, "Unknown scenario resource")
    snapshot = load_snapshot(case["snapshot_id"])
    source = next(f for f in snapshot.files if Path(f.path).name == (name or "index.html"))
    body = source.content
    if name in ("", "index.html"):
        body = body.replace('"/retail/', f'"/scenarios/{scenario_id}/retail/')
    return Response(
        body,
        media_type={"cart.js": "text/javascript", "styles.css": "text/css"}.get(name, "text/html"),
        headers={
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'none'; base-uri 'none'; form-action 'none'"
            )
        },
    )


@asynccontextmanager
async def browser_session() -> AsyncIterator[Browser]:
    # ASGI disconnect cancellation is level-triggered. Shield driver startup/teardown
    # so a closed HTTP client cannot cancel Playwright's own transport stop future.
    driver = None
    with anyio.CancelScope(shield=True):
        driver = await async_playwright().start()
    if driver is None:
        raise RuntimeError("Playwright driver startup was cancelled")
    browser: Browser | None = None
    try:
        browser = await driver.chromium.launch()
        yield browser
    finally:
        with anyio.CancelScope(shield=True):
            try:
                if browser is not None:
                    await browser.close()
            finally:
                await driver.stop()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Trusted reproduction runner", lifespan=lifespan)
app.mount("/retail", StaticFiles(directory=settings.fixture_dir, html=True), name="retail")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "fixed-recipe", "browser": "chromium"}


@app.post("/reproduce/{run_id}")
async def start(run_id: UUID, scenario_id: str = "cart-quantity") -> StreamingResponse:
    scenario(scenario_id)
    if run_id in active_ids or (settings.artifact_dir / str(run_id)).exists():
        raise HTTPException(409, "Run identifier already used")
    if len(active_ids) >= settings.max_active_runs:
        raise HTTPException(429, "Browser capacity reached")
    active_ids.add(run_id)

    async def stream() -> AsyncIterator[bytes]:
        try:
            async with asyncio.timeout(settings.run_timeout_seconds - 5):
                recipe = (
                    reproduce(run_id)
                    if scenario_id == "cart-quantity"
                    else reproduce_scenario(run_id, scenario_id)
                )
                async for line in recipe:
                    yield line
        except TimeoutError:
            yield event(
                "error", "Browser timed out", "Reproduction exceeded its browser execution budget."
            )
        except Exception:
            logger.exception("Reproduction failed for %s", run_id)
            yield event(
                "error",
                "Browser execution failed",
                "The runner could not complete the fixed reproduction. "
                "Inspect runner logs; no defect outcome was declared.",
            )
        finally:
            active_ids.discard(run_id)

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.get("/scenarios/{scenario_id}/retail/{name:path}")
async def scenario_file(scenario_id: str, name: str):
    return scenario_resource(scenario_id, name)
