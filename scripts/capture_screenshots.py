"""Capture the 8 submission screenshots with Playwright.

Waits for real Sentinel preview JPEGs so Gov-feed shots are not a black player.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://localhost:8080"
OUT = Path(__file__).resolve().parent.parent / "docs" / "submission" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

USERS = {
    "operator": "GUSIP@ops2026",
    "investigator": "GUSIP@inv2026",
    "coordinator": "GUSIP@coord2026",
    "admin": "GUSIP@admin2026",
}


def login(page: Page, username: str) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.locator("input").first.fill(username)
    page.locator("input[type=password]").fill(USERS[username])
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(f"{BASE}/", timeout=15_000)
    page.wait_for_load_state("networkidle")


def shot(page: Page, name: str) -> None:
    dst = OUT / name
    page.wait_for_timeout(400)
    page.screenshot(path=str(dst), full_page=False)
    print(f"  saved {dst.name}")


def click_tab(page: Page, label: str) -> None:
    btn = page.get_by_role("button", name=label, exact=True)
    if btn.count():
        btn.first.click()
        page.wait_for_timeout(400)


def wait_real_preview(page: Page, timeout_ms: int = 25000) -> None:
    """Wait until a Sentinel preview JPEG has actually decoded (not a 1px/error)."""
    try:
        page.wait_for_function(
            """() => [...document.images].some(i =>
                  i.naturalWidth > 120 && i.src.includes('/preview'))""",
            timeout=timeout_ms,
        )
    except Exception as exc:
        print(f"  warn: no real preview yet ({exc.__class__.__name__})")
        page.wait_for_timeout(2000)


def click_gov_tile(page: Page, index: int = 0) -> None:
    tile = page.get_by_role("button").filter(has_text="SEN-").nth(index)
    if tile.count():
        tile.click(force=True)
        page.wait_for_timeout(800)


def run_demo_scenario() -> None:
    print("  triggering stolen-vehicle corridor…")
    subprocess.Popen(
        ["docker", "compose", "exec", "-T", "worker", "python", "-m", "app.workers.demo_scenario"],
        cwd=Path(__file__).resolve().parent.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 950}, device_scale_factor=1)
        page = ctx.new_page()

        print("[1/8] login page")
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(800)
        shot(page, "01-login.png")

        print("[2/8] gov feeds — real Sentinel frames")
        login(page, "operator")
        click_tab(page, "Gov feeds")
        click_gov_tile(page, 0)
        wait_real_preview(page)
        click_tab(page, "Gov feeds")
        click_gov_tile(page, 0)
        page.wait_for_timeout(800)
        shot(page, "02-gov-feeds.png")

        print("[3/8] enlarged official camera (real frame)")
        click_tab(page, "Gov feeds")
        click_gov_tile(page, 2)
        wait_real_preview(page)
        click_tab(page, "Gov feeds")
        page.wait_for_timeout(800)
        shot(page, "03-own-demo-focus.png")

        print("[4/8] GIS map")
        page.goto(f"{BASE}/map", wait_until="networkidle")
        page.wait_for_timeout(3500)
        shot(page, "04-gis.png")

        print("[5/8] investigate — plate search")
        page.goto(f"{BASE}/search", wait_until="networkidle")
        page.get_by_role("button", name="Search").first.click()
        page.wait_for_timeout(2500)
        shot(page, "05-investigate.png")

        print("[6/8] watchlist")
        page.goto(f"{BASE}/login", wait_until="networkidle")
        login(page, "investigator")
        page.goto(f"{BASE}/watchlist", wait_until="networkidle")
        page.wait_for_timeout(1500)
        shot(page, "06-watchlist.png")

        print("[7/8] alerts inbox")
        page.goto(f"{BASE}/alerts", wait_until="networkidle")
        page.wait_for_timeout(1500)
        shot(page, "07-alerts.png")

        print("[8/8] coordinator — home dept + break-glass")
        page.goto(f"{BASE}/login", wait_until="networkidle")
        login(page, "coordinator")
        click_tab(page, "Own/demo")
        page.wait_for_timeout(1800)
        shot(page, "08-rbac-coordinator.png")

        browser.close()

    print(f"\nAll shots written to {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
