"""Evaluation-only final probes. Not copied into images, source context, or MCP tools.

These run after the repair loop has terminated and never provide revision feedback.
"""

from pathlib import Path

from workbench.repair.verifier import observation


async def score(browser, screenshot: Path):
    context = await browser.new_context(service_workers="block", accept_downloads=False)
    page = await context.new_page()
    page.set_default_timeout(3000)
    allowed = {"http://127.0.0.1:8080/retail/" + n for n in ("", "cart.js", "styles.css")}
    await context.route(
        "**/*",
        lambda route: route.continue_() if route.request.url in allowed else route.abort(),
    )
    checks = []
    try:
        await page.goto("http://127.0.0.1:8080/retail/", timeout=5000)
        await page.locator("#add-to-cart").click()
        for value, expected in [
            ("-12", 1),
            ("0", 1),
            ("2", 2),
            ("4", 4),
            ("7", 7),
            ("9", 9),
            ("12", 9),
            ("3.9", 3),
            ("", 1),
        ]:
            await page.goto("http://127.0.0.1:8080/retail/", timeout=5000)
            await page.locator("#add-to-cart").click()
            await page.locator("#quantity").fill(value)
            await page.locator("#quantity").dispatch_event("change")
            checks.append(await observation(page, f"final-input-{value or 'blank'}", expected))
        # New transition sequence, with intermediate quantities not used by feedback suite.
        for _ in range(5):
            await page.locator("#add-to-cart").click()
        checks.append(await observation(page, "final-add-six", 6))
        await page.locator("#decrease").click()
        checks.append(await observation(page, "final-decrease-five", 5))
        await page.locator("#increase").click()
        checks.append(await observation(page, "final-increase-six", 6))
        await page.screenshot(path=screenshot)
        return {
            "status": "passed" if all(c["passed"] for c in checks) else "failed",
            "checks": checks,
            "visibility": "evaluation_only_after_final_candidate",
            "version": "retail-final-v1",
        }
    finally:
        await context.close()
