"""E2E test for v0.11 Strategy Lab page."""

import pytest
from playwright.sync_api import Page, expect

BASE = "http://localhost:5173"


def _wait_react(page: Page, timeout: int = 8000):
    """Wait for React to hydrate."""
    import time
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        html = page.locator("#root").inner_html()
        if len(html) > 50:
            return
        page.wait_for_timeout(500)
    raise TimeoutError("React did not hydrate in time")


class TestV011Lab:
    def test_lab_page_loads(self, page: Page):
        page.goto(BASE + "/lab", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        root = page.locator("#root")
        html = root.inner_html()
        assert len(html) > 200, "Lab page did not render"

    def test_lab_has_signal_editor(self, page: Page):
        page.goto(BASE + "/lab", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        # Should have some signal-related UI elements
        content = page.content().lower()
        assert "signal" in content or "entry" in content or "rsi" in content, \
            "No signal editor content found"

    def test_lab_has_backtest_button(self, page: Page):
        page.goto(BASE + "/lab", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content().lower()
        assert "backtest" in content or "回测" in content, \
            "No backtest button found"

    def test_lab_screenshot(self, page: Page):
        page.goto(BASE + "/lab", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        page.screenshot(path="tests/e2e/artifacts/v011_lab_page.png")
