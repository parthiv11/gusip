"""Indian vehicle registration plate normalisation (AIS-189 / MoRTH formats)."""

from __future__ import annotations

import re

# GJ 01 AB 1234, GJ01AB1234, GJ-01-AB-1234, BH 12 AB 1234, 22 BH 1234 AB
PLATE_RE = re.compile(r"[^A-Z0-9]")


def normalize_plate(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = PLATE_RE.sub("", raw.upper())
    return cleaned or None


def format_plate(normalized: str | None) -> str | None:
    if not normalized:
        return None
    # Bharat series: 22BH1234AB
    if len(normalized) >= 10 and normalized[2:4] == "BH":
        return f"{normalized[:2]} BH {normalized[4:8]} {normalized[8:]}"
    # Standard: GJ01AB1234
    if len(normalized) >= 9:
        return f"{normalized[:2]} {normalized[2:4]} {normalized[4:6]} {normalized[6:]}"
    return normalized


def plate_state(normalized: str | None) -> str | None:
    if not normalized or len(normalized) < 2:
        return None
    if normalized[2:4] == "BH":
        return "BH"
    return normalized[:2]
