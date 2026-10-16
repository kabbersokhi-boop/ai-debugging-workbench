import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anyio
import pytest

from workbench import runner


async def test_disconnect_cancellation_finishes_browser_and_driver_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed: list[str] = []

    async def close_browser() -> None:
        await asyncio.sleep(0)
        completed.append("browser")

    async def stop_driver() -> None:
        await asyncio.sleep(0)
        completed.append("driver")

    browser = SimpleNamespace(close=AsyncMock(side_effect=close_browser))
    driver = SimpleNamespace(
        chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)),
        stop=AsyncMock(side_effect=stop_driver),
    )
    monkeypatch.setattr(
        runner, "async_playwright", lambda: SimpleNamespace(start=AsyncMock(return_value=driver))
    )
    ready = anyio.Event()

    async def request_task() -> None:
        async with runner.browser_session():
            ready.set()
            await anyio.sleep_forever()

    async with anyio.create_task_group() as group:
        group.start_soon(request_task)
        await ready.wait()
        group.cancel_scope.cancel()
    assert completed == ["browser", "driver"]


async def test_failed_browser_launch_still_stops_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = SimpleNamespace(
        chromium=SimpleNamespace(launch=AsyncMock(side_effect=RuntimeError("launch failed"))),
        stop=AsyncMock(),
    )
    monkeypatch.setattr(
        runner, "async_playwright", lambda: SimpleNamespace(start=AsyncMock(return_value=driver))
    )
    with pytest.raises(RuntimeError, match="launch failed"):
        async with runner.browser_session():
            pytest.fail("A failed browser must never be yielded")
    driver.stop.assert_awaited_once()
