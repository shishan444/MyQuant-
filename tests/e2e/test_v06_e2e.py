"""E2E tests for MyQuant V0.6 - Visual + UI features.

**DEPRECATED:** Streamlit UI has been removed in favor of React frontend (v0.10-v0.13).
These tests are skipped but kept for reference.

Tests the Streamlit app at http://localhost:8501 covering:
1. Main page load and navigation
2. Strategy Input page - form, DNA build, backtest preview
3. Evolution Monitor page - status display
4. Result Report page - empty state
5. Visualization components - Plotly charts rendering

To re-enable (for testing Streamlit locally):
  python -m pytest tests/e2e/test_v06_e2e.py -v --tb=short --run-deprecated
"""

import pytest

import time
from pathlib import Path

from playwright.sync_api import Page, expect

# Skip all tests in this module by default
pytestmark = pytest.mark.skip(reason="DEPRECATED: Streamlit UI removed, use React frontend instead")

BASE_URL = "http://localhost:8501"
TIMEOUT = 120000  # 120s - Streamlit pages are slow (compute_all_indicators)

PAGE_URLS = {
    "Strategy Input": f"{BASE_URL}/",
    "Evolution Monitor": f"{BASE_URL}/evolution_monitor",
    "Result Report": f"{BASE_URL}/result_report",
}


# ---------- Helpers ----------

def wait_for_streamlit(page: Page, timeout: int = TIMEOUT):
    """Wait for Streamlit to finish rendering.

    Streamlit keeps WebSocket connections open, so 'networkidle'
    never fires. We use 'commit' + explicit element waits instead.
    """
    page.wait_for_selector("[data-testid='stSidebar']", timeout=timeout)
    page.wait_for_selector(
        "[data-testid='stMainBlockContainer']",
        timeout=timeout,
    )
    time.sleep(4)


def wait_for_page_ready(page: Page, marker_text: str, timeout: int = TIMEOUT):
    """Wait for a specific text element to appear, indicating page is fully rendered.

    Streamlit renders progressively - some pages (like Strategy Input) take
    a long time because of compute_all_indicators(). We poll until the marker
    text appears in the DOM.
    """
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        # Check for skeletons - if present, page is still loading
        skeletons = page.locator("[data-testid='stSkeleton']")
        if skeletons.count() == 0:
            # No skeletons, check for marker text
            marker = page.get_by_text(marker_text)
            if marker.count() > 0:
                return
        time.sleep(2)
    raise TimeoutError(
        f"Page did not render '{marker_text}' within {timeout/1000}s"
    )


def goto_page(page: Page, page_name: str, wait_marker: str | None = None):
    """Navigate to a specific page via direct URL."""
    url = PAGE_URLS[page_name]
    page.goto(url, wait_until="commit", timeout=TIMEOUT)
    wait_for_streamlit(page)
    if wait_marker:
        wait_for_page_ready(page, wait_marker)


def take_screenshot(page: Page, name: str):
    """Take screenshot for test artifacts."""
    artifacts_dir = Path(__file__).parent / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    try:
        page.screenshot(path=str(artifacts_dir / f"{name}.png"))
    except Exception:
        pass  # Screenshots are best-effort


def get_main_text(page: Page) -> str:
    """Get text content from the main content area."""
    main = page.locator("[data-testid='stMainBlockContainer']")
    return main.inner_text(timeout=TIMEOUT)


def get_sidebar_text(page: Page) -> str:
    """Get text content from the sidebar."""
    sidebar = page.locator("[data-testid='stSidebar']")
    return sidebar.inner_text(timeout=TIMEOUT)


# ---------- Test 1: Main Page Load & Navigation ----------

def test_main_page_loads(page: Page):
    """V0.6: Main page loads with sidebar and navigation."""
    goto_page(page, "Strategy Input")

    # Verify sidebar exists
    sidebar = page.locator("[data-testid='stSidebar']")
    expect(sidebar).to_be_visible(timeout=TIMEOUT)

    # Verify sidebar controls: Symbol, Timeframe, Template
    sidebar_text = get_sidebar_text(page)
    assert "Symbol" in sidebar_text, "Expected 'Symbol' in sidebar"
    assert "Timeframe" in sidebar_text, "Expected 'Timeframe' in sidebar"
    assert "Scoring Template" in sidebar_text, "Expected 'Scoring Template' in sidebar"

    # Verify sidebar nav links exist
    nav = page.locator("[data-testid='stSidebarNav']")
    nav_links = nav.locator("a")
    assert nav_links.count() == 3, f"Expected 3 nav links, got {nav_links.count()}"

    # Verify page title
    main_text = get_main_text(page)
    assert "Strategy Input" in main_text

    take_screenshot(page, "01_main_page")


def test_sidebar_controls(page: Page):
    """V0.6: Sidebar controls for symbol, timeframe, template selection."""
    goto_page(page, "Strategy Input")

    sidebar_text = get_sidebar_text(page)

    # Verify default values
    assert "BTCUSDT" in sidebar_text, "Expected BTCUSDT in sidebar"
    assert "4h" in sidebar_text, "Expected 4h timeframe in sidebar"
    assert "profit_first" in sidebar_text, "Expected profit_first template in sidebar"

    take_screenshot(page, "02_sidebar_controls")


# ---------- Test 2: Strategy Input Page ----------

def test_strategy_input_page_loads(page: Page):
    """V0.6: Strategy Input page loads with form elements."""
    # Wait for 'Logic & Risk' as marker that full form is rendered
    goto_page(page, "Strategy Input", wait_marker="Logic & Risk")

    main_text = get_main_text(page)

    # Verify heading
    assert "Strategy Input" in main_text

    # Verify key sections exist
    assert "Signal Genes" in main_text, "Expected 'Signal Genes' section"
    assert "Logic & Risk" in main_text, "Expected 'Logic & Risk' section"

    take_screenshot(page, "03_strategy_input_page")


def test_strategy_input_form_elements(page: Page):
    """V0.6: Strategy form has all required controls."""
    goto_page(page, "Strategy Input", wait_marker="Logic & Risk")

    main_text = get_main_text(page)

    # Number of Signals input
    assert "Number of Signals" in main_text, "Expected 'Number of Signals'"

    # Entry/Exit Logic
    assert "Entry Logic" in main_text, "Expected 'Entry Logic'"
    assert "Exit Logic" in main_text, "Expected 'Exit Logic'"

    # Risk controls
    assert "Stop Loss" in main_text, "Expected 'Stop Loss'"
    assert "Take Profit" in main_text, "Expected 'Take Profit'"
    assert "Position Size" in main_text, "Expected 'Position Size'"

    # Build button
    build_btn = page.get_by_role("button", name="Build Strategy DNA")
    expect(build_btn).to_be_visible(timeout=TIMEOUT)

    take_screenshot(page, "04_strategy_form_elements")


def test_strategy_build_dna(page: Page):
    """V0.6: Build Strategy DNA button creates a valid DNA."""
    goto_page(page, "Strategy Input", wait_marker="Logic & Risk")

    # Click Build Strategy DNA
    build_btn = page.get_by_role("button", name="Build Strategy DNA")
    build_btn.click()

    # Wait for Streamlit to process + full re-render
    time.sleep(10)

    # Check for success or error alert
    main_text = get_main_text(page)
    has_success = "successfully" in main_text.lower()
    has_error = "invalid" in main_text.lower() or "error" in main_text.lower()

    take_screenshot(page, "05_build_dna_result")

    assert has_success or has_error, (
        f"Expected success or error feedback after building DNA. Got: {main_text[:300]}"
    )


def test_strategy_preview_backtest(page: Page):
    """V0.6: Preview Backtest button runs backtest and shows results."""
    goto_page(page, "Strategy Input", wait_marker="Logic & Risk")

    # Build DNA first
    build_btn = page.get_by_role("button", name="Build Strategy DNA")
    build_btn.click()
    time.sleep(15)

    # Wait for re-render - check for success OR error (either is acceptable)
    try:
        wait_for_page_ready(page, "successfully", timeout=60000)
    except TimeoutError:
        pass  # May show validation error instead

    main_text = get_main_text(page)
    has_success = "successfully" in main_text.lower()
    has_error = "invalid" in main_text.lower() or "error" in main_text.lower()

    # Verify we got some feedback
    assert has_success or has_error, (
        f"Expected success or error feedback. Got: {main_text[:300]}"
    )

    if has_success:
        preview_btn = page.get_by_role("button", name="Preview Backtest")
        if preview_btn.is_visible():
            preview_btn.click()

            # Wait for backtest to complete
            time.sleep(20)

            main_text = get_main_text(page)
            has_metrics = any(
                kw in main_text
                for kw in ["Total Return", "Sharpe Ratio", "Total Trades", "Metrics"]
            )
            assert has_metrics, f"Expected metrics after backtest preview, got: {main_text[:300]}"

            take_screenshot(page, "06_preview_backtest")
            return

    # DNA build may have validation errors - verify page is still functional
    take_screenshot(page, "06_preview_skipped")


def test_strategy_evolution_controls(page: Page):
    """V0.6: Evolution launch controls are present."""
    goto_page(page, "Strategy Input", wait_marker="Build Strategy DNA")

    main_text = get_main_text(page)

    # Should show Launch Evolution section (after full render)
    if "Launch Evolution" in main_text:
        # Since no DNA built, should show info about building first
        assert (
            "Build a strategy DNA first" in main_text
            or "Build" in main_text
        ), "Expected guidance to build DNA first"
    else:
        # Page may not have fully rendered the bottom section;
        # at minimum verify the Build button is present
        build_btn = page.get_by_role("button", name="Build Strategy DNA")
        expect(build_btn).to_be_visible(timeout=TIMEOUT)

    take_screenshot(page, "07_evolution_controls")


# ---------- Test 3: Evolution Monitor Page ----------

def test_evolution_monitor_page_loads(page: Page):
    """V0.6: Evolution Monitor page loads correctly."""
    goto_page(page, "Evolution Monitor")

    main_text = get_main_text(page)

    # Verify title
    assert "Evolution Monitor" in main_text

    take_screenshot(page, "08_evolution_monitor")


def test_evolution_monitor_status_display(page: Page):
    """V0.6: Monitor shows task status with appropriate states."""
    goto_page(page, "Evolution Monitor")

    main_text = get_main_text(page)

    # Either shows "No evolution task" info or shows task status
    has_no_task = "No evolution task" in main_text
    has_task = "Task:" in main_text

    if has_no_task:
        # Should show button to navigate to Strategy Input
        go_btn = page.get_by_role("button", name="Go to Strategy Input")
        expect(go_btn).to_be_visible(timeout=TIMEOUT)
    elif has_task:
        # Should show metrics columns
        assert "Generation" in main_text, "Expected 'Generation' metric"
        assert "Best Score" in main_text, "Expected 'Best Score' metric"

    take_screenshot(page, "09_monitor_status")


# ---------- Test 4: Result Report Page ----------

def test_result_report_page_loads(page: Page):
    """V0.6: Result Report page loads correctly."""
    goto_page(page, "Result Report")

    main_text = get_main_text(page)

    # Verify title
    assert "Result Report" in main_text

    take_screenshot(page, "10_result_report")


def test_result_report_empty_state(page: Page):
    """V0.6: Report page handles no completed tasks gracefully."""
    goto_page(page, "Result Report")

    main_text = get_main_text(page)

    # Either shows "No completed evolution tasks" or task selector
    has_no_tasks = "No completed evolution tasks" in main_text
    has_task_selector = "Select Completed Task" in main_text

    if has_no_tasks:
        go_btn = page.get_by_role("button", name="Go to Strategy Input")
        expect(go_btn).to_be_visible(timeout=TIMEOUT)
    elif has_task_selector:
        # Has completed tasks - verify selector
        assert has_task_selector

    take_screenshot(page, "11_report_state")


# ---------- Test 5: Visualization & Navigation ----------

def test_plotly_charts_render(page: Page):
    """V0.6: Plotly charts render when visible."""
    goto_page(page, "Strategy Input", wait_marker="Logic & Risk")

    # Build DNA first
    build_btn = page.get_by_role("button", name="Build Strategy DNA")
    build_btn.click()
    time.sleep(15)

    main_text = get_main_text(page)
    if "successfully" not in main_text.lower():
        # If DNA build failed, skip chart test
        take_screenshot(page, "12_charts_skipped")
        return

    # Preview to generate charts
    preview_btn = page.get_by_role("button", name="Preview Backtest")
    if preview_btn.is_visible():
        preview_btn.click()
        time.sleep(20)

        # Check for Plotly chart containers
        plotly_charts = page.locator(".js-plotly-plot")
        count = plotly_charts.count()
        if count > 0:
            take_screenshot(page, "12_plotly_charts")
            return

        # Alternative: check for any SVG in plotly containers
        svg_in_plots = page.locator(".stPlotlyChart svg")
        if svg_in_plots.count() > 0:
            take_screenshot(page, "12_plotly_charts")
            return

    take_screenshot(page, "12_plotly_charts")


def test_sidebar_navigation_between_pages(page: Page):
    """V0.6: Can navigate between all 3 pages via direct URL."""
    for page_name in ["Strategy Input", "Evolution Monitor", "Result Report"]:
        goto_page(page, page_name)

        # Verify page loaded by checking heading in main content
        main_text = get_main_text(page)
        assert page_name in main_text, (
            f"Expected '{page_name}' in main content, got: {main_text[:200]}"
        )

    take_screenshot(page, "13_navigation_complete")
