#!/usr/bin/env python3
"""Generate a narration track for GUSIP-demo.mp4 using edge-tts (free,
no API key, works headlessly) and mux it under the video.

Narration lines mirror the on-screen captions in remotion/src/meta.ts plus a
short line for the title and end cards. Each clip is placed at its caption's
timeline offset with a small lead-in so the voice starts just before the text
appears; if a narration clip runs longer than the caption's on-screen window,
downstream clips are pushed back so nothing overlaps or gets cut.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path

import edge_tts

ROOT = Path("/home/codespace/gusip")
SUB = ROOT / "docs/submission"
REMOTION = SUB / "remotion"
VOICE_DIR = SUB / "video-raw/voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

VOICE = "en-US-GuyNeural"
TITLE_SEC = 3.5
LEAD_IN = 0.15

meta = (REMOTION / "src/meta.ts").read_text()
raw_duration = float(re.search(r"RAW_DURATION_SEC = ([\d.]+)", meta).group(1))
timeline = json.loads(re.search(r"TIMELINE.*?=\s*(\[.*\]);", meta, re.S).group(1))

TITLE_LINE = "GUSIP. One wall. The cameras stay where they are."
END_LINE = "Video stays on the NVR. Hits, stills, and the GIS line come here."

lines = [{"t": 0.4, "text": TITLE_LINE, "video_offset": 0.0}]
for entry in timeline:
    lines.append({"t": entry["t"], "text": entry["label"], "video_offset": TITLE_SEC})
end_start = TITLE_SEC + raw_duration + 0.3
lines.append({"t": end_start, "text": END_LINE, "video_offset": 0.0})


async def synth(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate="+4%")
    await communicate.save(str(out_path))


async def main() -> None:
    clips = []
    for i, line in enumerate(lines):
        mp3 = VOICE_DIR / f"line{i:02d}.mp3"
        await synth(line["text"], mp3)
        dur = float(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(mp3)]
            ).strip()
        )
        clips.append({"path": mp3, "start": line["t"] + line["video_offset"] - LEAD_IN, "dur": dur})

    # Push back any clip that would overlap the previous one's tail.
    for i in range(1, len(clips)):
        min_start = clips[i - 1]["start"] + clips[i - 1]["dur"] + 0.1
        if clips[i]["start"] < min_start:
            clips[i]["start"] = min_start

    total_dur = TITLE_SEC + raw_duration + 4.0
    inputs = []
    filter_parts = []
    for i, c in enumerate(clips):
        inputs += ["-i", str(c["path"])]
        delay_ms = max(0, round(c["start"] * 1000))
        filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
    mix_inputs = "".join(f"[a{i}]" for i in range(len(clips)))
    filter_complex = ";".join(filter_parts) + f";{mix_inputs}amix=inputs={len(clips)}:duration=longest:dropout_transition=0[aout]"

    voice_track = SUB / "video-raw/voiceover.m4a"
    subprocess.check_call(
        ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
         "-map", "[aout]", "-t", f"{total_dur:.2f}", "-c:a", "aac", "-b:a", "160k", str(voice_track)]
    )
    print(f"Wrote {voice_track} ({voice_track.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
