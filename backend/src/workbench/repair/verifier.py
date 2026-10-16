"""Trusted behavioral checks. Never shipped in the candidate image or model context."""

import hashlib
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Page

VERIFIER_VERSION = hashlib.sha256(
    Path(__file__).read_bytes() + Path(__file__).with_name("broker.py").read_bytes()
).hexdigest()
CHECK_NAMES = [
    "empty-bag",
    "add-one-baseline",
    "increment-two",
    "increment-three",
    "decrement-two",
    "lower-limit",
    "upper-limit",
    "decrement-eight",
    "clamp-zero",
    "clamp-large",
    "invalid-input",
    "repeated-add-limit",
]


def dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


async def observation(page: Page, name: str, quantity: int) -> dict[str, Any]:
    # Independent expectations: integer arithmetic, not target JS or data-cents.
    subtotal = quantity * 6400
    shipping = 800 if 0 < subtotal < 10000 else 0
    expected = {
        "unit-price": "$64.00 each",
        "line-total": dollars(subtotal),
        "subtotal": dollars(subtotal),
        "shipping": dollars(shipping),
        "total": dollars(subtotal + shipping),
        "bag-count": str(quantity),
        "item-count": f"{quantity} {'item' if quantity == 1 else 'items'}",
    }
    raw_text = {key: await page.get_by_test_id(key).inner_text() for key in expected}
    output_truncated = any(len(text) > 200 for text in raw_text.values())
    actual = {key: text.strip()[:200] for key, text in raw_text.items()}
    quantity_value = await page.locator("#quantity").input_value()
    output_truncated = output_truncated or len(quantity_value) > 50
    controls = {
        "quantity": quantity_value[:50],
        "decrease_disabled": await page.locator("#decrease").is_disabled(),
        "increase_disabled": await page.locator("#increase").is_disabled(),
        "empty_visible": await page.locator("#empty").is_visible(),
        "item_visible": await page.locator("#cart-item").is_visible(),
    }
    expected_controls = {
        "quantity": str(quantity or 1),
        "decrease_disabled": quantity <= 1,
        "increase_disabled": quantity >= 9,
        "empty_visible": quantity == 0,
        "item_visible": quantity > 0,
    }
    visible_keys = ["subtotal", "shipping", "total"]
    if quantity:
        visible_keys += ["line-total", "unit-price"]
    visible_money = all([await page.get_by_test_id(key).is_visible() for key in visible_keys])
    return {
        "name": name,
        "quantity": quantity,
        "expected": expected,
        "observed": actual,
        "expected_controls": expected_controls,
        "controls": controls,
        "monetary_text_visible": visible_money,
        "output_truncated": output_truncated,
        "passed": (
            actual == expected
            and controls == expected_controls
            and visible_money
            and not output_truncated
        ),
    }


async def verify(browser: Browser, candidate_hash: str, screenshot: Path) -> dict[str, Any]:
    context = await browser.new_context(
        viewport={"width": 1160, "height": 880}, service_workers="block", accept_downloads=False
    )
    page = await context.new_page()
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)[:300]) if len(errors) < 5 else None)
    # Only immutable target resources. Even local CDP and other containers are blocked.
    allowed = {
        "http://127.0.0.1:8080/retail/",
        "http://127.0.0.1:8080/retail/cart.js",
        "http://127.0.0.1:8080/retail/styles.css",
    }
    await context.route(
        "**/*", lambda route: route.continue_() if route.request.url in allowed else route.abort()
    )
    try:
        await page.goto("http://127.0.0.1:8080/retail/", timeout=10000)
        await page.locator("#add-to-cart").wait_for()
        checks.append(await observation(page, "empty-bag", 0))
        await page.locator("#add-to-cart").click()
        checks.append(await observation(page, "add-one-baseline", 1))
        await page.locator("#increase").click()
        checks.append(await observation(page, "increment-two", 2))
        await page.locator("#increase").click()
        checks.append(await observation(page, "increment-three", 3))
        await page.screenshot(path=screenshot)
        await page.locator("#decrease").click()
        checks.append(await observation(page, "decrement-two", 2))
        await page.locator("#quantity").fill("1")
        await page.locator("#quantity").dispatch_event("change")
        checks.append(await observation(page, "lower-limit", 1))
        await page.locator("#quantity").fill("9")
        await page.locator("#quantity").dispatch_event("change")
        checks.append(await observation(page, "upper-limit", 9))
        await page.locator("#decrease").click()
        checks.append(await observation(page, "decrement-eight", 8))
        for name, value, expected in [
            ("clamp-zero", "0", 1),
            ("clamp-large", "99", 9),
            ("invalid-input", "", 1),
        ]:
            await page.locator("#quantity").fill(value)
            await page.locator("#quantity").dispatch_event("change")
            checks.append(await observation(page, name, expected))
        for _ in range(12):
            await page.locator("#add-to-cart").click()
        checks.append(await observation(page, "repeated-add-limit", 9))
        return {
            "candidate_hash": candidate_hash,
            "verifier_version": VERIFIER_VERSION,
            "procedure": "retail-pricing-browser-v1",
            "check_names": CHECK_NAMES,
            "checks": checks,
            "page_errors": errors[:5],
            "status": "passed"
            if len(checks) == len(CHECK_NAMES) and all(c["passed"] for c in checks) and not errors
            else "failed",
            "browser_version": browser.version,
            ("scope"): (
                "Named visible-price, quantity-control and baseline checks only; "
                "no universal correctness claim."
            ),
        }
    finally:
        await context.close()
