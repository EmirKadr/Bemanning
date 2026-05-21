import re

import pytest

from tools import visual_smoke


playwright_api = pytest.importorskip("playwright.sync_api")
PlaywrightError = playwright_api.Error
expect = playwright_api.expect
sync_playwright = playwright_api.sync_playwright


@pytest.fixture(scope="module")
def local_activity_server(tmp_path_factory):
    output_dir = tmp_path_factory.mktemp("legacy-activity-browser")
    base_url, server = visual_smoke.start_local_server(output_dir)
    try:
        yield base_url
    finally:
        server.close()


@pytest.fixture(scope="module")
def chromium_browser():
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            message = str(exc)
            if "Executable doesn't exist" in message or "playwright install" in message:
                pytest.skip("Playwright Chromium is not installed")
            raise
        try:
            yield browser
        finally:
            browser.close()


def login_admin(page, base_url: str) -> None:
    page.goto(f"{base_url}/login.html", wait_until="networkidle")
    page.fill("#username", "admin")
    page.fill("#password", "admin123")
    page.click("button.primary")
    page.wait_for_url("**/index.html", timeout=15000)
    page.wait_for_selector("#scheduleTable", timeout=15000)


def assert_activity_ui_is_canonical(page) -> None:
    page.wait_for_selector("#acts-body", timeout=15000)

    assert page.evaluate("location.pathname") == "/aktiviteter.html"
    assert "Ställen" not in page.title()
    expect(page.locator(".section-title")).to_have_text("Aktiviteter")
    expect(page.get_by_role("link", name="Aktiviteter")).to_be_visible()

    body_text = page.locator("body").inner_text(timeout=15000)
    assert "Ställen" not in body_text
    assert "Ställen / aktiviteter" not in body_text


def test_legacy_stallen_page_redirects_to_canonical_activity_ui(local_activity_server, chromium_browser):
    context = chromium_browser.new_context(locale="sv-SE")
    page = context.new_page()
    try:
        login_admin(page, local_activity_server)
        page.goto(f"{local_activity_server}/stallen.html", wait_until="networkidle")
        page.wait_for_url(re.compile(r".*/aktiviteter\.html(?:\?.*)?$"), timeout=15000)

        assert_activity_ui_is_canonical(page)
    finally:
        context.close()


def test_direct_activity_page_never_renders_legacy_label(local_activity_server, chromium_browser):
    context = chromium_browser.new_context(locale="sv-SE")
    page = context.new_page()
    try:
        login_admin(page, local_activity_server)
        page.goto(f"{local_activity_server}/aktiviteter.html", wait_until="networkidle")

        assert_activity_ui_is_canonical(page)
    finally:
        context.close()
