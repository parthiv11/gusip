#!/usr/bin/env python3
"""Burn the timeline captions from remotion/src/meta.ts onto the raw walkthrough
footage via ffmpeg drawtext.

Remotion's own OffthreadVideo compositing turned out to be pathologically slow
in this sandbox (2 CPUs): rendering the ~3950-frame composition was projected
at 4+ hours and repeatedly timed out on video-decode frames, while a
video-free range (title/end cards, pure DOM/CSS) rendered in seconds. So the
title and end cards are still rendered with Remotion/React (fast, no video
decode); this script does the equivalent of Remotion's CaptionOverlay but as
a single native ffmpeg pass over the footage, which comfortably keeps pace.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path("/home/codespace/gusip")
REMOTION = ROOT / "docs/submission/remotion"
RAW_WEBM = next((ROOT / "docs/submission/video-raw/native").glob("*.webm"))
CAPTIONS_DIR = ROOT / "docs/submission/video-raw/captions"
OUT = ROOT / "docs/submission/video-raw/walkthrough-captioned.mp4"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FADE = 0.35

CAPTIONS_DIR.mkdir(parents=True, exist_ok=True)

meta = (REMOTION / "src/meta.ts").read_text()
duration = float(re.search(r"RAW_DURATION_SEC = ([\d.]+)", meta).group(1))
timeline = json.loads(re.search(r"TIMELINE.*?=\s*(\[.*\]);", meta, re.S).group(1))

filters = []
for i, entry in enumerate(timeline):
    start = entry["t"]
    end = timeline[i + 1]["t"] if i + 1 < len(timeline) else duration
    txt_path = CAPTIONS_DIR / f"cap{i:02d}.txt"
    txt_path.write_text(entry["label"])
    fade_in_end = min(start + FADE, end)
    fade_out_start = max(end - FADE, start)
    alpha = (
        f"if(lt(t,{start}),0,"
        f"if(lt(t,{fade_in_end}),(t-{start})/{FADE},"
        f"if(lt(t,{fade_out_start}),1,"
        f"if(lt(t,{end}),({end}-t)/{FADE},0))))"
    )
    filters.append(
        "drawtext="
        f"fontfile={FONT}:textfile={txt_path}:"
        "fontcolor=0xf4e6c0:fontsize=28:"
        "x=60:y=h-th-56:"
        "box=1:boxcolor=0x140e06@0.94:boxborderw=24:"
        f"enable='between(t,{start},{end})':alpha='{alpha}'"
    )

filter_complex = ",".join(filters)

subprocess.check_call(
    [
        "ffmpeg", "-y", "-i", str(RAW_WEBM),
        "-vf", filter_complex,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", "30", "-an",
        str(OUT),
    ]
)
print(f"Wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
