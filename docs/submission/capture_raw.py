#!/usr/bin/env python3
"""Capture clean walkthrough footage (no burned-in captions/title cards) for
the Remotion edit in docs/submission/remotion.

Uses Playwright's native video recording instead of the old CDP-screencast +
frame-averaging approach in record_demo.py. That approach only received a
screencast frame on repaint, then assembled the JPEGs at a single average fps
(n_frames / elapsed) — which silently compresses long static holds (the exact
moments meant to give a viewer time to read a caption) since those periods
produce almost no frames. A 157.8s walkthrough came out as a 71s video. Native
recording captures real wall-clock time, so playback speed matches actual
elapsed time and Remotion's caption timings (from timeline.json) land where
they should.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

ROOT = Path("/home/codespace/gusip")
OUT = ROOT / "docs/submission/remotion/public"
RAW_DIR = ROOT / "docs/submission/video-raw/native"
BASE = "http://localhost:8080"

OUT.mkdir(parents=True, exist_ok=True)
if RAW_DIR.exists():
    shutil.rmtree(RAW_DIR)
RAW_DIR.mkdir(parents=True)

timeline: list[dict] = []
t0 = 0.0


def mark(label: str) -> None:
    timeline.append({"t": round(time.time() - t0, 2), "label": label})


def hold(page: Page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def login(page: Page, user: str, password: str) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_selector("input")
    page.locator("input").first.fill(user)
    page.locator("input[type=password]").fill(password)
    hold(page, 1.2)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=25000)
    page.wait_for_timeout(900)


def click_wall_tab(page: Page, label: str) -> None:
    tab = page.get_by_role("tab", name=label, exact=True)
    try:
        tab.click(timeout=10_000)
    except PWTimeout:
        # Under memory pressure a click can stall past its timeout even
        # though the element resolved fine — dispatch the click event
        # directly rather than crash a multi-minute recording over it.
        tab.dispatch_event("click")


def click_nav(page: Page, label: str) -> None:
    dest = {"Control Room": "/", "Investigate": "/search", "Cameras": "/cameras", "GIS": "/map"}[label]
    link = page.locator("header nav a", has_text=label).first
    try:
        if link.count() and link.is_visible():
            link.click(timeout=10_000)
        else:
            page.goto(f"{BASE}{dest}")
    except PWTimeout:
        page.goto(f"{BASE}{dest}")
    page.wait_for_timeout(700)


def run_corridor() -> subprocess.Popen:
    return subprocess.Popen(
        ["docker", "compose", "exec", "-T", "worker", "python", "-m", "app.workers.demo_scenario"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def walkthrough(page: Page) -> None:
    login(page, "operator", "GUSIP@ops2026")
    mark("Operator wall. Video stays on departmental NVRs — this is the hit picture.")
    hold(page, 2.5)

    click_wall_tab(page, "Gov feeds")
    mark("Gov feeds — official Sentinel cameras, proxied live through GUSIP")
    hold(page, 1.5)
    sync_btn = page.get_by_role("button", name="Sync Sentinel")
    if sync_btn.count():
        sync_btn.click()
        try:
            page.wait_for_selector("text=government feeds onboarded", timeout=45000)
        except PWTimeout:
            page.wait_for_timeout(3000)
    else:
        page.wait_for_timeout(1000)

    mark("Chimanbhai Bridge — jury-provided Sentinel camera, live through the GUSIP proxy.")
    for label in ("SEN-1", "Chimanbhai", "Bridge"):
        tile = page.get_by_text(label, exact=False).first
        try:
            if tile.count():
                tile.click(timeout=4000)
                break
        except PWTimeout:
            continue
    hold(page, 16)

    try:
        page.get_by_text("SEN-15", exact=False).first.click(timeout=3000)
        mark("Same wall, next official camera. Live stream from the Sentinel evaluation wall.")
        hold(page, 10)
    except PWTimeout:
        hold(page, 3)

    click_wall_tab(page, "Own/demo")
    mark("Own/demo wall — RTSP / ONVIF / vendor cameras. Watchlist: stolen Fortuner GJ 01 ST 0001.")
    hold(page, 3)

    proc = run_corridor()
    mark("Corridor firing: Paldi / SG Highway / Thaltej / Gandhinagar. Target: inbox under 8 seconds.")
    try:
        page.get_by_text("GJ 01 ST 0001", exact=False).first.wait_for(timeout=25000)
        mark("Hit landed — GJ 01 ST 0001 flagged on the wall.")
    except PWTimeout:
        page.wait_for_timeout(8000)
    hold(page, 10)
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()

    mark("Investigate — purpose is mandatory and audited. Operators cannot export CSV.")
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
    mark("GIS polyline: five hops, two cities. One line instead of three phone calls.")
    hold(page, 6)

    click_nav(page, "GIS")
    mark("Statewide GIS — cameras, coverage, yellow pins for open alerts.")
    hold(page, 6)

    page.evaluate("() => sessionStorage.clear()")
    page.context.clear_cookies()
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    mark("Coordinator (Ahmedabad) — home district only, until break-glass.")
    hold(page, 2)
    login(page, "coordinator", "GUSIP@coord2026")
    mark("Ahmedabad coordinator. Cameras outside home district are hidden.")
    click_nav(page, "Cameras")
    hold(page, 6)

    page.get_by_role("button", name="Break-glass").click()
    mark("Break-glass: FIR reason is audited. Access expires on a timer even if they forget to End.")
    hold(page, 2)
    page.get_by_role("button", name="Grant access").click()
    try:
        page.wait_for_selector("text=Break-glass statewide", timeout=10000)
    except PWTimeout:
        page.wait_for_timeout(2000)
    hold(page, 3)
    click_nav(page, "Cameras")
    mark("Statewide cameras unlocked for 30 minutes. End now returns the coordinator to Ahmedabad.")
    hold(page, 7)
    try:
        page.get_by_role("button", name="End now").click(timeout=4000)
        hold(page, 4)
    except PWTimeout:
        pass


def main() -> None:
    global t0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(RAW_DIR),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        t0 = time.time()
        try:
            walkthrough(page)
        finally:
            context.close()
        video_path = page.video.path()
        browser.close()

    webm = Path(video_path)
    mp4 = OUT / "walkthrough.mp4"
    subprocess.check_call(
        [
            "ffmpeg", "-y", "-i", str(webm),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-an", str(mp4),
        ]
    )
    duration = float(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(mp4)]
        ).strip()
    )

    meta_ts = ROOT / "docs/submission/remotion/src/meta.ts"
    meta_ts.write_text(
        "// Generated by docs/submission/capture_raw.py — do not hand-edit.\n"
        f"export const RAW_DURATION_SEC = {duration:.3f};\n"
        f"export const TIMELINE: {{ t: number; label: string }}[] = {json.dumps(timeline, indent=2)};\n"
    )
    print(f"Wrote {mp4} ({mp4.stat().st_size / 1e6:.1f} MB, {duration:.1f}s)")
    print(f"Wrote {meta_ts} ({len(timeline)} timeline marks)")


if __name__ == "__main__":
    main()
