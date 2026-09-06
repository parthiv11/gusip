"""Looping MP4s when the official Sentinel portal is login-gated."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from app.services.storage import DATA_DIR

PREVIEW_DIR = DATA_DIR / "previews"

log = logging.getLogger("gusip.local_feed")
LOOP_DIR = DATA_DIR / "loops"


def _run_ffmpeg(args: list[str]) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args],
            capture_output=True,
            timeout=40,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("ffmpeg loop failed: %s", exc)
        return False
    if result.returncode != 0:
        err = (result.stderr or b"").decode("utf-8", "ignore")[-300:]
        log.warning("ffmpeg loop exited %s: %s", result.returncode, err)
        return False
    return True


def ensure_still_loop(sentinel_id: str) -> Path | None:
    """Turn the last ANPR JPEG into a short looping H.264 clip."""
    sid = "".join(ch for ch in sentinel_id if ch.isalnum() or ch in {"-", "_"})
    if not sid:
        return None
    src = PREVIEW_DIR / f"SEN-{sid}.jpg"
    if not src.is_file():
        return None
    LOOP_DIR.mkdir(parents=True, exist_ok=True)
    out = LOOP_DIR / f"SEN-{sid}.mp4"
    if out.is_file() and out.stat().st_mtime >= src.stat().st_mtime and out.stat().st_size > 1000:
        return out
    tmp = out.with_suffix(".tmp.mp4")
    ok = _run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(src),
            "-t",
            "24",
            "-vf",
            "scale=640:-2:flags=lanczos,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-an",
            "-movflags",
            "+faststart",
            str(tmp),
        ]
    )
    if not ok or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        return out if out.is_file() and out.stat().st_size > 1000 else None
    tmp.replace(out)
    return out


def ensure_demo_loop() -> Path | None:
    """Shared placeholder clip for departmental (non-Sentinel) cameras."""
    LOOP_DIR.mkdir(parents=True, exist_ok=True)
    out = LOOP_DIR / "demo.mp4"
    if out.is_file() and out.stat().st_size > 1000:
        return out
    tmp = out.with_suffix(".tmp.mp4")
    ok = _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=10",
            "-t",
            "6",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-an",
            "-movflags",
            "+faststart",
            str(tmp),
        ]
    )
    if not ok or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        return out if out.is_file() and out.stat().st_size > 1000 else None
    tmp.replace(out)
    return out
