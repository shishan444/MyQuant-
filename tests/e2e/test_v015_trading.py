"""E2E tests for the Trading page (v0.15+).

Covers: empty state, page load, navigation, console errors, layout components.
Full CRUD tests (create/pause/stop/delete) require a running backend with data
and are intentionally kept as smoke tests.
"""

import pytest
from playwright.sync_api import Page

import os
BASE = os.environ.get("E2E_WEB_URL", "http://localhost:8080")


def _wait_react(page: Page, timeout: int = 8000):
    """Wait for React to hydrate by polling for content in #root."""
    import time
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        html = page.locator("#root").inner_html()
        if len(html) > 50:
            return
        page.wait_for_timeout(500)
    raise TimeoutError("React did not hydrate in time")


def _goto_trading(page: Page):
    """Navigate to trading page and wait for React hydration."""
    page.goto(BASE + "/trading", timeout=10000)
    page.wait_for_load_state("domcontentloaded", timeout=10000)
    _wait_react(page)


class TestTradingPageLoad:
    """Trading page renders without console errors."""

    def test_no_console_errors(self, page: Page):
        errors: list[str] = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        _goto_trading(page)
        page.wait_for_timeout(2000)
        filtered = [
            e for e in errors
            if "favicon" not in e.lower()
            and "devtools" not in e.lower()
            and "net::" not in e.lower()
            and "failed to load resource" not in e.lower()
        ]
        assert len(filtered) == 0, f"Console errors on /trading: {filtered}"

    def test_page_has_content(self, page: Page):
        _goto_trading(page)
        html = page.locator("#root").inner_html()
        assert len(html) > 200, f"Trading page has too little content: {len(html)} chars"


class TestTradingEmptyState:
    """When no tasks exist, the empty state UI renders correctly."""

    def test_empty_state_or_task_list_renders(self, page: Page):
        """Page shows either empty state or task list (depends on backend state)."""
        _goto_trading(page)
        content = page.content()
        # Either empty state text or task-related content
        has_empty = "暂无模拟交易任务" in content or "前往策略库" in content
        has_tasks = "任务" in content or "运行" in content or "停止" in content or "暂停" in content
        assert has_empty or has_tasks, "Trading page shows neither empty state nor tasks"

    def test_empty_state_has_navigation_button(self, page: Page):
        """If empty state is shown, it has a link to strategies page."""
        _goto_trading(page)
        content = page.content()
        if "暂无模拟交易任务" in content:
            # Check for navigation button
            strategies_btn = page.locator("button:has-text('前往策略库'), a:has-text('前往策略库')")
            assert strategies_btn.count() > 0, "Go to Strategies button missing in empty state"


class TestTradingNavigation:
    """Navigation between Trading and other pages."""

    def test_trading_sidebar_link_exists(self, page: Page):
        page.goto(BASE, timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        trading_link = page.locator("nav a[href='/trading']")
        assert trading_link.count() >= 1, "No sidebar link found for /trading"

    def test_navigate_to_trading_via_sidebar(self, page: Page):
        page.goto(BASE, timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        trading_link = page.locator("nav a[href='/trading']").first
        trading_link.click()
        page.wait_for_timeout(1000)
        assert "/trading" in page.url, f"Expected /trading in URL, got {page.url}"

    def test_direct_url_access(self, page: Page):
        _goto_trading(page)
        html = page.locator("#root").inner_html()
        assert len(html) > 200, "Trading page not accessible via direct URL"


class TestTradingLayout:
    """Layout components render correctly on trading page."""

    def test_header_title(self, page: Page):
        _goto_trading(page)
        header = page.locator("header")
        assert header.is_visible(), "Header not visible"
        title = header.locator("h1")
        title_text = title.text_content() or ""
        assert "模拟交易" in title_text or "交易" in title_text, \
            f"Expected 模拟交易 in header title, got '{title_text}'"

    def test_sidebar_visible(self, page: Page):
        _goto_trading(page)
        sidebar = page.locator("aside")
        assert sidebar.is_visible(), "Sidebar not visible"


class TestTradingHeader:
    """Test page-level header elements."""

    def test_trading_page_renders(self, page: Page):
        """trading 页正常渲染(当前前端 header 仅标题, 无独立 RunnerStatusBadge——
        旧版'Runner Online/Offline'断言基于已移除组件, 改为验证 header + 内容区)."""
        _goto_trading(page)
        page.wait_for_timeout(2000)
        assert page.locator("header").is_visible(), "Header not visible"
        content = page.locator("body").inner_text()
        assert "模拟交易" in content, "trading 页内容未渲染"
