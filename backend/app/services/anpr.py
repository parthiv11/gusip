"""ANPR helpers: extract Indian plates from noisy OCR text."""

from __future__ import annotations

import re

from app.core.plates import format_plate, normalize_plate

STANDARD = re.compile(r"([A-Z]{2})(\d{1,2})([A-Z]{1,3})(\d{4})")
BHARAT = re.compile(r"(\d{2})BH(\d{4})([A-Z]{1,2})")
CONFUSABLES = str.maketrans({"O": "0", "I": "1", "Q": "0", "S": "5", "B": "8"})


def _fix_digit_runs(text: str) -> str:
    """Apply 0/O style fixes only inside likely digit groups."""
    return text.upper().replace(" ", "").replace("-", "")


def extract_plates(ocr_text: str) -> list[tuple[str, float]]:
    if not ocr_text:
        return []
    raw = re.sub(r"[^A-Z0-9]+", " ", ocr_text.upper())
    compact = raw.replace(" ", "")
    found: dict[str, float] = {}

    def add(norm: str | None, conf: float) -> None:
        if not norm or len(norm) < 8:
            return
        found[norm] = max(found.get(norm, 0.0), conf)

    for m in STANDARD.finditer(compact):
        add(normalize_plate("".join(m.groups())), 0.82)
    for m in BHARAT.finditer(compact):
        add(normalize_plate("".join(m.groups())), 0.8)

    # OCR often merges GJ 01 AB 1234 with junk; sliding window of 8–12 chars
    for i in range(0, max(0, len(compact) - 7)):
        window = compact[i : i + 12]
        for m in STANDARD.finditer(window):
            add(normalize_plate("".join(m.groups())), 0.7)

    return [(format_plate(n) or n, c) for n, c in found.items()]
