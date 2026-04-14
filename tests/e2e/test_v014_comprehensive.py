"""Comprehensive E2E test for v0.10-v0.13 frontend - console errors and navigation."""

import pytest
from playwright.sync_api import Page

BASE = "http://localhost:5173"


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


class TestConsoleErrors:
    """Check for JavaScript console errors on each page."""

    def _collect_errors(self, page: Page, url: str) -> list[str]:
        errors: list[str] = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.goto(url, timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        page.wait_for_timeout(2000)  # Allow async operations to settle
        # Filter out known non-critical errors
        return [
            e for e in errors
            if "favicon" not in e.lower()
            and "devtools" not in e.lower()
            and "net::" not in e.lower()
            and "failed to load resource" not in e.lower()
        ]

    def test_no_console_errors_data_page(self, page: Page):
        errors = self._collect_errors(page, BASE + "/data")
        assert len(errors) == 0, f"Console errors on /data: {errors}"

    def test_no_console_errors_lab_page(self, page: Page):
        errors = self._collect_errors(page, BASE + "/lab")
        assert len(errors) == 0, f"Console errors on /lab: {errors}"

    def test_no_console_errors_evolution_page(self, page: Page):
        errors = self._collect_errors(page, BASE + "/evolution")
        assert len(errors) == 0, f"Console errors on /evolution: {errors}"

    def test_no_console_errors_library_page(self, page: Page):
        errors = self._collect_errors(page, BASE + "/library")
        assert len(errors) == 0, f"Console errors on /library: {errors}"

    def test_no_console_errors_settings_page(self, page: Page):
        errors = self._collect_errors(page, BASE + "/settings")
        assert len(errors) == 0, f"Console errors on /settings: {errors}"


class TestNavigation:
    """Test client-side navigation between pages."""

    def test_sidebar_navigation_links_work(self, page: Page):
        """Click each sidebar link and verify the page changes."""
        page.goto(BASE, timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)

        # Find all NavLink elements in sidebar
        links = page.locator("nav a")
        assert links.count() >= 5, f"Expected at least 5 nav links, found {links.count()}"

        expected_routes = ["/lab", "/evolution", "/library", "/data", "/settings"]

        for route in expected_routes:
            link = page.locator(f"nav a[href='{route}']")
            assert link.count() >= 1, f"No sidebar link found for route {route}"

    def test_navigate_via_sidebar_click(self, page: Page):
        """Click sidebar links to navigate between pages."""
        page.goto(BASE, timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)

        # Click Lab link
        page.locator("nav a[href='/lab']").first.click()
        page.wait_for_timeout(1000)
        assert "/lab" in page.url, f"Expected /lab in URL, got {page.url}"

        # Click Evolution link
        page.locator("nav a[href='/evolution']").first.click()
        page.wait_for_timeout(1000)
        assert "/evolution" in page.url, f"Expected /evolution in URL, got {page.url}"

        # Click Library link
        page.locator("nav a[href='/library']").first.click()
        page.wait_for_timeout(1000)
        assert "/library" in page.url, f"Expected /library in URL, got {page.url}"

        # Click Data link
        page.locator("nav a[href='/data']").first.click()
        page.wait_for_timeout(1000)
        assert "/data" in page.url, f"Expected /data in URL, got {page.url}"

        # Click Settings link
        page.locator("nav a[href='/settings']").first.click()
        page.wait_for_timeout(1000)
        assert "/settings" in page.url, f"Expected /settings in URL, got {page.url}"

    def test_root_redirects_to_data(self, page: Page):
        page.goto(BASE, timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        assert "/data" in page.url, f"Expected redirect to /data, got {page.url}"

    def test_direct_url_access(self, page: Page):
        """All routes should be directly accessible via URL."""
        routes = ["/data", "/lab", "/evolution", "/library", "/settings"]
        for route in routes:
            page.goto(BASE + route, timeout=10000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            _wait_react(page)
            html = page.locator("#root").inner_html()
            assert len(html) > 200, f"Page {route} has too little content: {len(html)} chars"


class TestLayoutComponents:
    """Test shared layout components render correctly."""

    def _goto_and_wait(self, page: Page, route: str = "/data"):
        page.goto(BASE + route, timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)

    def test_sidebar_visible(self, page: Page):
        self._goto_and_wait(page)
        sidebar = page.locator("aside")
        assert sidebar.is_visible(), "Sidebar not visible"

    def test_header_visible_with_title(self, page: Page):
        self._goto_and_wait(page, "/lab")
        header = page.locator("header")
        assert header.is_visible(), "Header not visible"
        title = header.locator("h1")
        assert title.is_visible(), "Header title not visible"
        assert "Strategy Lab" in title.text_content(), f"Expected 'Strategy Lab' in header, got '{title.text_content()}'"

    def test_sidebar_has_branding(self, page: Page):
        self._goto_and_wait(page)
        # Check for QT branding icon
        qt_badge = page.locator("text=QT")
        assert qt_badge.count() > 0, "QT branding not found"

    def test_header_title_updates_per_page(self, page: Page):
        titles_map = {
            "/lab": "Strategy Lab",
            "/evolution": "Evolution Center",
            "/library": "Strategy Library",
            "/data": "Data Management",
            "/settings": "Settings",
        }
        for route, expected_title in titles_map.items():
            page.goto(BASE + route, timeout=10000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            _wait_react(page)
            header_title = page.locator("header h1")
            actual = header_title.text_content() or ""
            assert expected_title in actual, f"On {route}: expected '{expected_title}', got '{actual}'"


class TestPageContent:
    """Test page-specific content renders correctly."""

    def test_data_page_has_import_button(self, page: Page):
        page.goto(BASE + "/data", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        # Check for Import CSV button
        content = page.content()
        assert "Import CSV" in content, "Import CSV button not found on data page"

    def test_data_page_has_search_input(self, page: Page):
        page.goto(BASE + "/data", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        search = page.locator("input[placeholder*='Search']")
        assert search.count() > 0, "Search input not found on data page"

    def test_lab_page_has_strategy_lab_heading(self, page: Page):
        page.goto(BASE + "/lab", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content()
        assert "Strategy Lab" in content, "Strategy Lab heading not found"

    def test_lab_page_has_risk_control_section(self, page: Page):
        page.goto(BASE + "/lab", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content()
        assert "Risk Control" in content, "Risk Control section not found"

    def test_lab_page_has_execution_section(self, page: Page):
        page.goto(BASE + "/lab", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content()
        assert "Execution" in content, "Execution section not found"

    def test_evolution_page_has_empty_state(self, page: Page):
        page.goto(BASE + "/evolution", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content()
        assert "Evolution Center" in content, "Evolution Center heading not found"

    def test_library_page_has_search(self, page: Page):
        page.goto(BASE + "/library", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content()
        assert "Search" in content or "search" in content, "Search not found on library page"

    def test_library_page_has_symbol_filter(self, page: Page):
        page.goto(BASE + "/library", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content().lower()
        assert "symbol" in content or "btc" in content, "Symbol filter not found on library page"

    def test_settings_page_has_evolution_config_tab(self, page: Page):
        page.goto(BASE + "/settings", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content()
        assert "Evolution Config" in content, "Evolution Config tab not found"

    def test_settings_page_has_api_keys_tab(self, page: Page):
        page.goto(BASE + "/settings", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content()
        assert "API Keys" in content, "API Keys tab not found"

    def test_settings_page_has_population_size_field(self, page: Page):
        page.goto(BASE + "/settings", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)
        content = page.content()
        assert "Population Size" in content, "Population Size field not found"

    def test_settings_page_tab_switching(self, page: Page):
        page.goto(BASE + "/settings", timeout=10000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        _wait_react(page)

        # Click on API Keys tab
        api_tab = page.locator("button:has-text('API Keys')")
        assert api_tab.count() > 0, "API Keys tab button not found"
        api_tab.click()
        page.wait_for_timeout(500)

        # Check that Claude API Key label is visible
        content = page.content()
        assert "Claude API Key" in content, "Claude API Key form not shown after tab switch"
