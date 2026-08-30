"""ANPR helpers: extract Indian plates from noisy OCR text."""

from __future__ import annotations

from collections import Counter
import re

from app.core.plates import format_plate, normalize_plate

STANDARD = re.compile(r"([A-Z]{2})(\d{1,2})([A-Z]{1,3})(\d{4})")
BHARAT = re.compile(r"(\d{2})BH(\d{4})([A-Z]{1,2})")
DATE_BLOCK = re.compile(r"(?:19|20)\d{6}|\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?:19|20)\d{2}")
OSD_TOKENS = re.compile(
    r"CSITMS|RLVD|PTZ|JUNCTION|PALDI|HOSPITAL|CAM(?:ERA)?\d+|SEN[- ]?\d+"
)

# MoRTH state / UT codes. Reject overlay junk like ES, ST, PS, IF as "states".
INDIAN_STATES = frozenset(
    {
        "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", "HP",
        "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL",
        "OD", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK", "UP", "WB",
    }
)


def _canonical_standard(state: str, rto: str, series: str, serial: str) -> str | None:
    if state not in INDIAN_STATES:
        return None
    if not rto.isdigit() or not (1 <= int(rto) <= 99):
        return None
    if not serial.isdigit() or len(serial) != 4:
        return None
    return f"{state}{int(rto):02d}{series}{serial}"


def vote_ocr_strings(texts: list[str]) -> str:
    """Majority vote per character. Recovers GJ01AB1234 from several noisy reads."""
    cleaned: list[str] = []
    for text in texts:
        compact = re.sub(r"[^A-Z0-9]", "", (text or "").upper())
        if 6 <= len(compact) <= 16:
            cleaned.append(compact)
    if not cleaned:
        return ""
    width = Counter(len(c) for c in cleaned).most_common(1)[0][0]
    same = [c for c in cleaned if len(c) == width]
    if len(same) == 1:
        return same[0]
    chars: list[str] = []
    for i in range(width):
        chars.append(Counter(c[i] for c in same).most_common(1)[0][0])
    return "".join(chars)


def extract_plates(ocr_text: str) -> list[tuple[str, float]]:
    if not ocr_text:
        return []
    voted = vote_ocr_strings(re.split(r"\s+", ocr_text))
    blob = f"{ocr_text} {voted}".strip()
    cleaned = OSD_TOKENS.sub(" ", blob.upper())
    cleaned = DATE_BLOCK.sub(" ", cleaned)
    raw = re.sub(r"[^A-Z0-9]+", " ", cleaned)
    compact = raw.replace(" ", "")
    found: dict[str, float] = {}

    def add(norm: str | None, conf: float) -> None:
        if not norm or len(norm) < 8:
            return
        found[norm] = max(found.get(norm, 0.0), conf)

    for m in STANDARD.finditer(compact):
        add(_canonical_standard(*m.groups()), 0.82)
    for m in BHARAT.finditer(compact):
        add(normalize_plate("".join(m.groups())), 0.8)

    for i in range(0, max(0, len(compact) - 7)):
        window = compact[i : i + 12]
        for m in STANDARD.finditer(window):
            add(_canonical_standard(*m.groups()), 0.7)

    return [(format_plate(n) or n, c) for n, c in found.items()]
