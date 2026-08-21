#!/usr/bin/env python3
"""Record the 1080p jury walkthrough: Gov feeds, stolen corridor, Investigate, break-glass."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

ROOT = Path("/home/codespace/gusip")
OUT = ROOT / "docs/submission"
RAW = OUT / "video-raw"
BASE = "http://localhost:8080"
MP4 = OUT / "GUSIP-demo.mp4"

TITLE = """<!DOCTYPE html><html><body style="margin:0;height:100vh;background:#0a0704;
font-family:Georgia,serif;color:#f4e6c0;display:grid;place-items:center;text-align:center">
<div>
<p style="letter-spacing:.28em;text-transform:uppercase;font:600 13px system-ui;color:#c9a227;margin:0 0 18px">
Gujarat Police Innovation Challenge 2026</p>
<h1 style="font-size:64px;margin:0 0 12px;font-weight:600">GUSIP</h1>
<p style="font:20px/1.4 system-ui;color:#d9ccb0;max-width:34em">
One wall. The cameras stay where they are.<br>
Official Sentinel feeds + stolen Fortuner GJ 01 ST 0001.
</p>
</div></body></html>"""

END = """<!DOCTYPE html><html><body style="margin:0;height:100vh;background:#0a0704;
font-family:Georgia,serif;color:#f4e6c0;display:grid;place-items:center;text-align:center">
<div>
<h1 style="font-size:48px;margin:0 0 16px">Video stays on the NVR.</h1>
<p style="font:20px/1.45 system-ui;color:#d9ccb0;max-width:32em">
Hits, stills, and the GIS line come here.<br>
localhost:8080 · operator / GUSIP@ops2026
</p>
</div></body></html>"""


def caption(page: Page, text: str) -> None:
    page.evaluate(
        """(t) => {
      let el = document.getElementById('gusip-rec-cap');
      if (!el) {
        el = document.createElement('div');
        el.id = 'gusip-rec-cap';
        Object.assign(el.style, {
          position: 'fixed', left: '0', right: '0', bottom: '0', zIndex: '2147483647',
          background: 'rgba(20,14,6,0.94)', color: '#f4e6c0',
          padding: '14px 32px 18px', font: '600 21px/1.35 system-ui, Segoe UI, sans-serif',
          borderTop: '3px solid #c9a227', pointerEvents: 'none',
        });
        document.body.appendChild(el);
      }
      el.textContent = t;
    }""",
        text,
    )


def hold(page: Page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def login(page: Page, user: str, password: str) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_selector("input")
    page.locator("input").first.fill(user)
    page.locator("input[type=password]").fill(password)
    hold(page, 1.4)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=25000)
    page.wait_for_timeout(800)


def click_nav(page: Page, label: str) -> None:
    link = page.locator("nav a", has_text=label).first
    if link.count() and link.is_visible():
        link.click()
    else:
        page.goto(f"{BASE}{ {'Control Room': '/', 'Investigate': '/search', 'Cameras': '/cameras', 'GIS': '/map'}.get(label, '/') }")
    page.wait_for_timeout(600)


def run_corridor() -> subprocess.Popen:
    return subprocess.Popen(
        ["docker", "compose", "exec", "-T", "worker", "python", "-m", "app.workers.demo_scenario"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def walkthrough(page: Page) -> None:
    page.set_content(TITLE)
    hold(page, 5)

    login(page, "operator", "GUSIP@ops2026")
    caption(page, "Operator wall. Video stays on departmental NVRs — this is the hit picture.")
    hold(page, 3)

    page.get_by_role("button", name="Gov feeds").click()
    caption(page, "Gov feeds — official cameras from live.sentinelgujarat.in")
    hold(page, 2)
    page.get_by_role("button", name="Sync Sentinel").click()
    try:
        page.wait_for_selector("text=government feeds onboarded", timeout=45000)
    except PWTimeout:
        page.wait_for_timeout(4000)

    caption(page, "Chimanbhai Bridge — jury-provided Sentinel camera, live through the GUSIP proxy.")
    for label in ("SEN-1", "Chimanbhai", "Bridge"):
        tile = page.get_by_text(label, exact=False).first
        try:
            if tile.count():
                tile.click(timeout=4000)
                break
        except PWTimeout:
            continue
    hold(page, 14)

    # Second official camera so it is obviously a wall, not one clip
    try:
        page.get_by_text("SEN-15", exact=False).first.click(timeout=3000)
        caption(page, "Same wall, next official camera. Progressive stream + JPEG fallback so the pane is never black.")
        hold(page, 8)
    except PWTimeout:
        hold(page, 3)

    page.get_by_role("button", name="Own/demo").click()
    caption(page, "Own/demo wall — RTSP / ONVIF / vendor cameras. Watchlist: stolen Fortuner GJ 01 ST 0001.")
    hold(page, 3)

    proc = run_corridor()
    caption(page, "Corridor firing: Paldi / SG Highway / Thaltej / Gandhinagar. Target: inbox under 8 seconds.")
    try:
        page.get_by_text("GJ 01 ST 0001", exact=False).first.wait_for(timeout=25000)
    except PWTimeout:
        page.wait_for_timeout(8000)
    hold(page, 10)
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()

    caption(page, "Investigate — purpose is mandatory and audited. Operators cannot export CSV.")
    click_nav(page, "Investigate")
    hold(page, 1.5)
    page.locator("select").select_option("evaluation")
    hold(page, 1)
    page.get_by_role("button", name="Search").click()
    try:
        page.wait_for_selector("text=hops", timeout=15000)
    except PWTimeout:
        pass
    hold(page, 8)
    caption(page, "GIS polyline: five hops, two cities. One line instead of three phone calls.")
    hold(page, 6)

    click_nav(page, "GIS")
    caption(page, "Statewide GIS — cameras, coverage, yellow pins for open alerts.")
    hold(page, 6)

    page.evaluate("() => localStorage.removeItem('gusip.session')")
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    caption(page, "Coordinator (Ahmedabad) — home district only, until break-glass.")
    hold(page, 2)
    login(page, "coordinator", "GUSIP@coord2026")
    caption(page, "Ahmedabad coordinator. Cameras outside home district are hidden.")
    click_nav(page, "Cameras")
    hold(page, 6)

    page.get_by_role("button", name="Break-glass").click()
    caption(page, "Break-glass: FIR reason is audited. Access expires on a timer even if they forget to End.")
    hold(page, 2)
    page.get_by_role("button", name="Grant access").click()
    try:
        page.wait_for_selector("text=Break-glass statewide", timeout=10000)
    except PWTimeout:
        page.wait_for_timeout(2000)
    hold(page, 3)
    click_nav(page, "Cameras")
    caption(page, "Statewide cameras unlocked for 30 minutes. End now returns the coordinator to Ahmedabad.")
    hold(page, 7)
    try:
        page.get_by_role("button", name="End now").click(timeout=4000)
        hold(page, 4)
    except PWTimeout:
        pass

    page.set_content(END)
    hold(page, 6)


def encode(webm: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(webm),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "22",
        "-preset",
        "medium",
        "-movflags",
        "+faststart",
        "-an",
        str(MP4),
    ]
    subprocess.check_call(cmd)
    print(f"Wrote {MP4} ({MP4.stat().st_size / 1e6:.1f} MB)")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    for old in RAW.glob("*"):
        old.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-web-security",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(RAW),
            record_video_size={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        try:
            walkthrough(page)
        except Exception as exc:
            caption(page, f"Recording note: {exc}")
            hold(page, 3)
            print("Walkthrough error:", exc, file=sys.stderr)
            raise
        finally:
            video = page.video
            context.close()
            browser.close()
            webm = Path(video.path()) if video else None

    if not webm or not webm.exists():
        found = list(RAW.glob("*.webm"))
        if not found:
            print("No webm recorded", file=sys.stderr)
            return 1
        webm = found[0]

    encode(webm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
