"""Conftest for E2E tests - configures Playwright browser."""

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args():
    # Use the Playwright-managed chromium (installed via `playwright install`).
    # The previous hardcoded executable_path pointed at a Linux cache path
    # (/home/ss/.cache/.../chromium-1217/chrome-linux64) that does not exist on
    # macOS or CI; omitting it lets Playwright locate the browser itself.
    return {
        "headless": True,
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
    }
