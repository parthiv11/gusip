"""License-plate localisation + OCR for low-resolution CCTV.

Neural SR on a single tiny crop hallucinates strokes. What works on PTZ:

1. Burst several real frames of the same bumper (multi-frame, not ESRGAN).
2. Align + median fuse, then CLAHE / unsharp upsample.
3. RapidOCR *recognition only* — the detector is empty on 10–20 px plates.
4. Character vote, then MoRTH ``extract_plates``.
"""

from __future__ import annotations

import logging
import re
import urllib.request
from collections import defaultdict, deque
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.config import get_settings

log = logging.getLogger("gusip.anpr")

PLATE_MODEL_URL = (
    "https://huggingface.co/morsetechlab/yolov11-license-plate-detection"
    "/resolve/main/license-plate-finetune-v1n.pt"
)

_plate_model: Any = None
_rapidocr: Any = None
_rapidocr_failed = False
_CROP_BANK: dict[str, deque[np.ndarray]] = defaultdict(lambda: deque(maxlen=6))
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _settings():
    return get_settings()


def get_plate_model() -> Any | None:
    """YOLO11n fine-tuned on Roboflow license-plate boxes. CPU, ~nano size."""
    global _plate_model
    if _plate_model is not None:
        return _plate_model if _plate_model is not False else None
    settings = _settings()
    if settings.inference_mode != "yolo":
        _plate_model = False
        return None
    try:
        from ultralytics import YOLO
    except Exception:
        log.warning("ultralytics missing; plate detector off")
        _plate_model = False
        return None
    path = Path(settings.inference_plate_model_path)
    try:
        if not path.exists() or path.stat().st_size < 1_000:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            log.info("Downloading plate detector %s", PLATE_MODEL_URL)
            # PLATE_MODEL_URL is a hardcoded constant above, not request input.
            urllib.request.urlretrieve(PLATE_MODEL_URL, tmp)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            tmp.replace(path)
        _plate_model = YOLO(str(path))
        log.info("Plate YOLO loaded %s", path)
        return _plate_model
    except Exception:
        log.exception("Plate YOLO failed to load")
        _plate_model = False
        return None


def _looks_like_indian_plate(x1: float, y1: float, x2: float, y2: float, frame_h: int | None = None) -> bool:
    """Reject square glare, OSD, and bus-sized false boxes. GJ plates are wide and small."""
    w = x2 - x1
    h = y2 - y1
    if w < 28 or h < 10 or w > 200 or h > 64:
        return False
    ar = w / max(h, 1.0)
    if ar < 1.55 or ar > 6.8:
        return False
    if frame_h:
        if y2 < 0.07 * frame_h or y1 > 0.93 * frame_h:
            return False
    return True


def _nms_boxes(
    boxes: list[tuple[float, float, float, float, float]], iou_thresh: float = 0.45
) -> list[tuple[float, float, float, float, float]]:
    if len(boxes) < 2:
        return boxes
    ordered = sorted(boxes, key=lambda b: b[4], reverse=True)
    keep: list[tuple[float, float, float, float, float]] = []
    while ordered:
        best = ordered.pop(0)
        keep.append(best)
        rest: list[tuple[float, float, float, float, float]] = []
        bx1, by1, bx2, by2, _ = best
        ba = max(1.0, (bx2 - bx1) * (by2 - by1))
        for cand in ordered:
            x1, y1, x2, y2, _s = cand
            ix1, iy1 = max(bx1, x1), max(by1, y1)
            ix2, iy2 = min(bx2, x2), min(by2, y2)
            inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            union = ba + max(1.0, (x2 - x1) * (y2 - y1)) - inter
            if inter / union < iou_thresh:
                rest.append(cand)
        ordered = rest
    return keep


def _predict_plate_xyxy(
    model: Any, rgb: np.ndarray, conf: float = 0.12, imgsz: int = 960, *, apply_osd: bool = True
) -> list[tuple[float, float, float, float, float]]:
    try:
        results = model.predict(rgb, verbose=False, device="cpu", imgsz=imgsz, conf=conf)
    except Exception:
        log.exception("Plate YOLO predict failed")
        return []
    frame_h = int(rgb.shape[0]) if apply_osd else None
    boxes: list[tuple[float, float, float, float, float]] = []
    for r in results:
        if r.boxes is None:
            continue
        for b in r.boxes:
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            score = float(b.conf[0]) if b.conf is not None else 0.0
            if not _looks_like_indian_plate(x1, y1, x2, y2, frame_h):
                continue
            boxes.append((x1, y1, x2, y2, score))
    return boxes


def _predict_plate_tiles(model: Any, rgb: np.ndarray) -> list[tuple[float, float, float, float, float]]:
    """Run the plate model on the lower FOV so 15–25 px plates are not downscaled away."""
    h, w = int(rgb.shape[0]), int(rgb.shape[1])
    y0 = int(h * 0.40)
    boxes: list[tuple[float, float, float, float, float]] = []
    slices: list[tuple[int, int, np.ndarray]] = [(0, y0, rgb[y0:h, :])]
    if w >= 1400:
        mid, overlap = w // 2, 160
        slices = [
            (0, y0, rgb[y0:h, 0 : mid + overlap]),
            (mid - overlap, y0, rgb[y0:h, mid - overlap : w]),
        ]
    for ox, oy, tile in slices:
        if tile.size == 0:
            continue
        for x1, y1, x2, y2, score in _predict_plate_xyxy(model, tile, conf=0.08, imgsz=960, apply_osd=False):
            boxes.append((x1 + ox, y1 + oy, x2 + ox, y2 + oy, score))
    return boxes


def detect_plate_boxes(
    jpeg: bytes, dets: list[dict[str, Any]] | None = None
) -> list[tuple[float, float, float, float, float]]:
    """Full-frame, lower-FOV tiles, then each vehicle crop — plates are 15–25 px on PTZ."""
    model = get_plate_model()
    if model is None or not jpeg:
        return []
    img = Image.open(BytesIO(jpeg)).convert("RGB")
    rgb = np.array(img)
    h, w = int(rgb.shape[0]), int(rgb.shape[1])
    found = _predict_plate_xyxy(model, rgb, conf=0.12, imgsz=1280)
    found.extend(_predict_plate_tiles(model, rgb))
    for det in _largest_vehicles(dets or [], h):
        vx1, vy1, vx2, vy2 = _vehicle_pad_box(det, w, h)
        crop = img.crop((vx1, vy1, vx2, vy2))
        if crop.width >= 48 and crop.height >= 28:
            found.extend(_scaled_plate_xyxy(model, crop, vx1, vy1, conf=0.08, imgsz=640, target=960))
        bumper_box = _bumper_box(det, w, h)
        if bumper_box is None:
            continue
        bx1, by1, bx2, by2 = bumper_box
        bumper = img.crop(bumper_box)
        found.extend(_scaled_plate_xyxy(model, bumper, bx1, by1, conf=0.06, imgsz=640, target=800))
        for cx1, cy1, cx2, cy2, score in _contour_plate_xyxy(np.array(bumper)):
            found.append((bx1 + cx1, by1 + cy1, bx1 + cx2, by1 + cy2, score))
    return _nms_boxes(
        [b for b in found if _looks_like_indian_plate(b[0], b[1], b[2], b[3], h)]
    )


def _scaled_plate_xyxy(
    model: Any,
    crop: Image.Image,
    ox: float,
    oy: float,
    *,
    conf: float,
    imgsz: int,
    target: int,
) -> list[tuple[float, float, float, float, float]]:
    if crop.width < 24 or crop.height < 10:
        return []
    scale = max(1.0, target / max(crop.width, crop.height))
    big = crop.resize(
        (max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )
    out: list[tuple[float, float, float, float, float]] = []
    for px1, py1, px2, py2, score in _predict_plate_xyxy(
        model, np.array(big), conf=conf, imgsz=imgsz, apply_osd=False
    ):
        out.append((ox + px1 / scale, oy + py1 / scale, ox + px2 / scale, oy + py2 / scale, score))
    return out


def _contour_plate_xyxy(rgb: np.ndarray) -> list[tuple[float, float, float, float, float]]:
    """Bright wide rectangles in a bumper crop — YOLO miss on night PTZ."""
    try:
        import cv2
    except Exception:
        return []
    if rgb.size == 0:
        return []
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) if rgb.ndim == 3 else rgb
    h, w = int(gray.shape[0]), int(gray.shape[1])
    if w < 32 or h < 12:
        return []
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, w // 18), 3))
    _, bright = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel)
    sobel = cv2.convertScaleAbs(cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3))
    _, edges = cv2.threshold(sobel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    boxes: list[tuple[float, float, float, float, float]] = []
    for mask in (bright, edges):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            if not _looks_like_indian_plate(x, y, x + bw, y + bh, None):
                continue
            ar = bw / max(bh, 1)
            if ar < 2.0 or bw > 140 or bh > 36:
                continue
            if bw > 0.72 * w and bh > 0.50 * h:
                continue
            boxes.append((float(x), float(y), float(x + bw), float(y + bh), 0.15))
    ranked = _nms_boxes(boxes, iou_thresh=0.4)
    ranked.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return ranked[:4]


def _vehicle_pad_box(det: dict[str, Any], w: int, h: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = float(det["x1"]), float(det["y1"]), float(det["x2"]), float(det["y2"])
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    return (
        max(0, int(x1 - 0.04 * bw)),
        max(0, int(y1 - 0.04 * bh)),
        min(w, int(x2 + 0.04 * bw)),
        min(h, int(y2 + 0.04 * bh)),
    )


def _largest_vehicles(dets: list[dict[str, Any]], frame_h: int, limit: int = 4) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for det in dets:
        if det.get("object_type") not in {"vehicle", "two-wheeler"}:
            continue
        x1, y1, x2, y2 = det.get("x1"), det.get("y1"), det.get("x2"), det.get("y2")
        if None in (x1, y1, x2, y2):
            continue
        bw = max(1.0, float(x2) - float(x1))
        bh = max(1.0, float(y2) - float(y1))
        close = float(y2) > 0.42 * max(frame_h, 1)
        min_w, min_h = (180, 90) if close else (240, 120)
        if bw < min_w or bh < min_h:
            continue
        scored.append((bw * bh * (1.35 if close else 1.0), det))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [det for _, det in scored[:limit]]


def _bumper_box(det: dict[str, Any], w: int, h: int) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = float(det["x1"]), float(det["y1"]), float(det["x2"]), float(det["y2"])
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    top_frac, bot_frac = (0.58, 1.08) if det.get("object_type") == "vehicle" else (0.48, 1.10)
    box = (
        max(0, int(x1 - 0.08 * bw)),
        max(0, int(y1 + top_frac * bh)),
        min(w, int(x2 + 0.08 * bw)),
        min(h, int(y1 + bot_frac * bh)),
    )
    if box[2] - box[0] < 16 or box[3] - box[1] < 6:
        return None
    return box


def _bumper_from_image(img: Image.Image, det: dict[str, Any]) -> Image.Image | None:
    box = _bumper_box(det, *img.size)
    if box is None:
        return None
    return img.crop(box)


def _is_ocrable_plate_crop(crop: Image.Image) -> bool:
    """Bumper bands are 300–800 px wide; those must not go to RapidOCR."""
    if crop.width < 22 or crop.height < 10:
        return False
    if crop.width > 220 or crop.height > 80:
        return False
    ar = crop.width / max(crop.height, 1)
    return 1.4 <= ar <= 8.0


def _crop_from_xyxy(
    img: Image.Image, x1: float, y1: float, x2: float, y2: float, *, pad_x: float, pad_y: float
) -> Image.Image | None:
    w, h = img.size
    box = (
        max(0, int(x1 - pad_x * max(1.0, x2 - x1))),
        max(0, int(y1 - pad_y * max(1.0, y2 - y1))),
        min(w, int(x2 + pad_x * max(1.0, x2 - x1))),
        min(h, int(y2 + pad_y * max(1.0, y2 - y1))),
    )
    crop = img.crop(box)
    if crop.width < 12 or crop.height < 6:
        return None
    return crop


def plate_crops(jpeg: bytes, dets: list[dict[str, Any]] | None = None) -> list[Image.Image]:
    """Tight plate boxes only. Bumper is a search region, never an OCR crop."""
    if not jpeg:
        return []
    img = Image.open(BytesIO(jpeg)).convert("RGB")
    crops: list[Image.Image] = []
    for x1, y1, x2, y2, _conf in detect_plate_boxes(jpeg, dets):
        crop = _crop_from_xyxy(img, x1, y1, x2, y2, pad_x=0.10, pad_y=0.22)
        if crop is not None and _is_ocrable_plate_crop(crop):
            crops.append(crop)
    return crops


def enhance_low_res(crop: Image.Image) -> Image.Image:
    """CLAHE + unsharp + upsample. Not neural SR — that invents false glyphs."""
    gray = crop.convert("L")
    arr = np.asarray(gray)
    try:
        import cv2

        clip = 2.2 if arr.size < 80 * 28 else 3.0
        tiles = (4, 4) if min(arr.shape[:2]) < 40 else (8, 8)
        arr = cv2.createCLAHE(clipLimit=clip, tileGridSize=tiles).apply(arr)
        blur = cv2.GaussianBlur(arr, (0, 0), 0.9)
        arr = cv2.addWeighted(arr, 1.7, blur, -0.7, 0)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    except Exception:
        gray = ImageOps.autocontrast(ImageEnhance.Contrast(gray).enhance(2.4))
        arr = np.asarray(gray.filter(ImageFilter.SHARPEN))
    img = Image.fromarray(arr)
    if img.height < 14:
        target_h = 72
    elif img.height < 24:
        target_h = 64
    else:
        target_h = max(48, img.height * 3)
    scale = target_h / max(img.height, 1)
    target_w = max(192, int(img.width * scale))
    return ImageOps.autocontrast(img.resize((target_w, target_h), Image.Resampling.LANCZOS))


def _sharpness(gray: np.ndarray) -> float:
    try:
        import cv2

        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        return float(gray.var())


def fuse_gray_crops(crops: list[np.ndarray]) -> np.ndarray:
    """ECC-align then median. Real extra photons beat a hallucinated 4x network."""
    if not crops:
        raise ValueError("no crops")
    if len(crops) == 1:
        return crops[0]
    try:
        import cv2
    except Exception:
        h = int(np.median([c.shape[0] for c in crops]))
        w = int(np.median([c.shape[1] for c in crops]))
        stacked = [np.array(Image.fromarray(c).resize((w, h))) for c in crops]
        return np.median(np.stack(stacked), axis=0).astype(np.uint8)

    h = max(8, int(np.median([c.shape[0] for c in crops])))
    w = max(16, int(np.median([c.shape[1] for c in crops])))
    resized = [
        cv2.resize(c, (w, h), interpolation=cv2.INTER_CUBIC) if c.shape[:2] != (h, w) else c
        for c in crops
    ]
    ref = max(resized, key=_sharpness)
    aligned = [ref]
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 1e-4)
    ref_f = ref.astype(np.float32) / 255.0
    for im in resized:
        if im is ref:
            continue
        try:
            warp = np.eye(2, 3, dtype=np.float32)
            _cc, warp = cv2.findTransformECC(
                ref_f,
                im.astype(np.float32) / 255.0,
                warp,
                cv2.MOTION_TRANSLATION,
                criteria,
            )
            aligned.append(
                cv2.warpAffine(im, warp, (w, h), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
            )
        except Exception:
            aligned.append(im)
    fused = np.median(np.stack(aligned), axis=0).astype(np.uint8)
    try:
        fused = cv2.fastNlMeansDenoising(fused, None, 6, 7, 21)
    except Exception:
        pass
    return fused


def _plate_variants(crop: Image.Image) -> list[Image.Image]:
    enhanced = enhance_low_res(crop)
    return [enhanced, ImageOps.invert(enhanced)]


def _get_rapidocr() -> Any | None:
    global _rapidocr, _rapidocr_failed
    if _rapidocr_failed:
        return None
    if _rapidocr is not None:
        return _rapidocr
    try:
        from rapidocr import RapidOCR

        _rapidocr = RapidOCR()
        log.info("RapidOCR (PP-OCR ONNX) ready")
        return _rapidocr
    except Exception:
        try:
            from rapidocr_onnxruntime import RapidOCR

            _rapidocr = RapidOCR()
            log.info("RapidOCR onnxruntime ready")
            return _rapidocr
        except Exception:
            _rapidocr_failed = True
            log.warning("RapidOCR not installed; Tesseract fallback")
            return None


def _parse_rapidocr(result: Any) -> list[str]:
    texts: list[str] = []
    if result is None:
        return texts
    for attr in ("txts", "texts"):
        val = getattr(result, attr, None)
        if val:
            texts.extend(str(t) for t in val if t)
            return texts
    rows = result[0] if isinstance(result, tuple) else result
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                txt = row.get("txt") or row.get("text")
                if txt:
                    texts.append(str(txt))
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                texts.append(str(row[1]))
    return texts


def _ocr_rapid(crop: Image.Image) -> str:
    engine = _get_rapidocr()
    if engine is None:
        return ""
    texts: list[str] = []
    for variant in _plate_variants(crop):
        arr = np.array(variant.convert("RGB"))
        try:
            result = engine(arr, use_det=False, use_cls=False, use_rec=True)
        except TypeError:
            try:
                result = engine(arr)
            except Exception:
                log.exception("RapidOCR failed")
                continue
        except Exception:
            log.exception("RapidOCR rec-only failed")
            continue
        chunk = " ".join(_parse_rapidocr(result))
        if chunk.strip():
            texts.append(chunk)
    return " ".join(texts)


def _ocr_tesseract(crop: Image.Image) -> str:
    try:
        import pytesseract
    except Exception:
        return ""
    texts: list[str] = []
    for variant in _plate_variants(crop):
        for psm in ("7", "8"):
            texts.append(
                pytesseract.image_to_string(
                    variant,
                    config=(
                        f"--oem 1 --psm {psm} "
                        "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                    ),
                )
            )
    return " ".join(texts)


def _latin_ocr_keep(text: str) -> str:
    """PP-OCR rec is Chinese-first; night glare becomes CJK / shop-sign junk."""
    if not text:
        return ""
    stripped = _CJK.sub(" ", text)
    kept = re.sub(r"[^A-Z0-9 ]", " ", stripped.upper())
    tokens = [tok for tok in kept.split() if tok]
    compact = "".join(tokens)
    if len(compact) < 4:
        return ""
    if len(re.findall(r"[A-Z]", compact)) < 2 or len(re.findall(r"\d", compact)) < 2:
        return ""
    return " ".join(tokens)


def _ocr_crop(crop: Image.Image) -> str:
    raw = " ".join(part for part in (_ocr_rapid(crop), _ocr_tesseract(crop)) if part.strip())
    return _latin_ocr_keep(raw)


def _bank_fuse(camera_key: str, track_id: str | None, gray: np.ndarray) -> Image.Image:
    if not camera_key or not track_id:
        return enhance_low_res(Image.fromarray(gray))
    key = f"{camera_key}:{track_id}"
    bank = _CROP_BANK[key]
    bank.append(gray)
    fused = fuse_gray_crops(list(bank))
    return enhance_low_res(Image.fromarray(fused))


def _crops_from_frames(
    frames: list[bytes], dets: list[dict[str, Any]], camera_key: str = ""
) -> list[Image.Image]:
    if not frames:
        return []
    last = frames[-1]
    img_last = Image.open(BytesIO(last)).convert("RGB")
    w, h = img_last.size
    images = [Image.open(BytesIO(frame)).convert("RGB") for frame in frames]
    out: list[Image.Image] = []

    def _fuse_box(box: tuple[int, int, int, int]) -> None:
        grays: list[np.ndarray] = []
        for img in images:
            crop = img.crop(box)
            if crop.width < 16 or crop.height < 8:
                continue
            grays.append(np.asarray(crop.convert("L")))
        if not grays:
            return
        fused = fuse_gray_crops(grays)
        sharp = grays[int(np.argmax([_sharpness(g) for g in grays]))]
        track_id = f"{box[0]}:{box[1]}:{box[2]}:{box[3]}"
        out.append(_bank_fuse(camera_key, track_id, fused))
        out.append(enhance_low_res(Image.fromarray(sharp)))

    for x1, y1, x2, y2, _conf in detect_plate_boxes(last, dets):
        crop = _crop_from_xyxy(img_last, x1, y1, x2, y2, pad_x=0.12, pad_y=0.24)
        if crop is None or not _is_ocrable_plate_crop(crop):
            continue
        _fuse_box(
            (
                max(0, int(x1 - 0.12 * max(1.0, x2 - x1))),
                max(0, int(y1 - 0.24 * max(1.0, y2 - y1))),
                min(w, int(x2 + 0.12 * max(1.0, x2 - x1))),
                min(h, int(y2 + 0.24 * max(1.0, y2 - y1))),
            )
        )
    return out


def read_plate_text(
    jpeg: bytes,
    extra_crops: list[Image.Image] | None = None,
    *,
    frames: list[bytes] | None = None,
    dets: list[dict[str, Any]] | None = None,
    camera_key: str = "",
) -> str:
    """OCR plate-localised crops only. Never run OCR on the full frame (OSD)."""
    if extra_crops is not None and not extra_crops and not frames:
        return ""
    crops: list[Image.Image] = []
    if frames and dets:
        crops.extend(_crops_from_frames(frames, dets, camera_key))
    if extra_crops:
        crops.extend(extra_crops)
    if not crops and jpeg:
        crops = plate_crops(jpeg, dets or [])
    texts: list[str] = []
    for crop in crops:
        enhanced = crop.mode == "L"
        if crop.width < 22 or crop.height < 10:
            continue
        if not enhanced and not _is_ocrable_plate_crop(crop):
            continue
        if _sharpness(np.asarray(crop.convert("L"))) < 4.0 and crop.height < 18:
            continue
        text = _ocr_crop(crop)
        if text.strip():
            texts.append(text)
    return " ".join(texts)
