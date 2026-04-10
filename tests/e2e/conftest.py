"""Conftest for E2E tests - configures Playwright browser."""

import pytest


CHROMIUM_PATH = "/home/ss/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {
        "executable_path": CHROMIUM_PATH,
        "headless": True,
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
    }
