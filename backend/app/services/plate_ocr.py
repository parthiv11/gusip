"""License-plate localisation + OCR for low-resolution CCTV.

Neural SR on a single tiny crop hallucinates strokes. What works on PTZ:

1. Burst several real frames of the same bumper (multi-frame, not ESRGAN).
2. Align + median fuse, then CLAHE / unsharp upsample.
3. RapidOCR *recognition only* — the detector is empty on 10–20 px plates.
4. Character vote, then MoRTH ``extract_plates``.
"""

from __future__ import annotations

import logging
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
            urllib.request.urlretrieve(PLATE_MODEL_URL, tmp)
            tmp.replace(path)
        _plate_model = YOLO(str(path))
        log.info("Plate YOLO loaded %s", path)
        return _plate_model
    except Exception:
        log.exception("Plate YOLO failed to load")
        _plate_model = False
        return None


def _predict_plate_xyxy(model: Any, rgb: np.ndarray, conf: float = 0.12) -> list[tuple[float, float, float, float, float]]:
    try:
        results = model.predict(rgb, verbose=False, device="cpu", imgsz=960, conf=conf)
    except Exception:
        log.exception("Plate YOLO predict failed")
        return []
    boxes: list[tuple[float, float, float, float, float]] = []
    for r in results:
        if r.boxes is None:
            continue
        for b in r.boxes:
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            score = float(b.conf[0]) if b.conf is not None else 0.0
            if x2 - x1 < 8 or y2 - y1 < 4:
                continue
            boxes.append((x1, y1, x2, y2, score))
    return boxes


def detect_plate_boxes(
    jpeg: bytes, dets: list[dict[str, Any]] | None = None
) -> list[tuple[float, float, float, float, float]]:
    """Full-frame first, then each vehicle crop upscaled — plates are tiny on PTZ CCTV."""
    model = get_plate_model()
    if model is None or not jpeg:
        return []
    img = Image.open(BytesIO(jpeg)).convert("RGB")
    boxes = _predict_plate_xyxy(model, np.array(img))
    if boxes:
        return boxes
    w, h = img.size
    found: list[tuple[float, float, float, float, float]] = []
    for det in _largest_vehicles(dets or [], h):
        vx1, vy1, vx2, vy2 = _vehicle_pad_box(det, w, h)
        crop = img.crop((vx1, vy1, vx2, vy2))
        if crop.width < 24 or crop.height < 16:
            continue
        scale = max(1.0, 960 / max(crop.width, crop.height))
        big = crop.resize(
            (max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
            Image.Resampling.LANCZOS,
        )
        for px1, py1, px2, py2, score in _predict_plate_xyxy(model, np.array(big), conf=0.08):
            found.append(
                (
                    vx1 + px1 / scale,
                    vy1 + py1 / scale,
                    vx1 + px2 / scale,
                    vy1 + py2 / scale,
                    score,
                )
            )
    return found


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
        min_w, min_h = (32, 16) if close else (50, 28)
        if bw < min_w or bh < min_h:
            continue
        scored.append((bw * bh * (1.35 if close else 1.0), det))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [det for _, det in scored[:limit]]


def _bumper_from_image(img: Image.Image, det: dict[str, Any]) -> Image.Image | None:
    w, h = img.size
    x1, y1, x2, y2 = float(det["x1"]), float(det["y1"]), float(det["x2"]), float(det["y2"])
    bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
    top_frac, bot_frac = (0.58, 1.08) if det.get("object_type") == "vehicle" else (0.48, 1.10)
    box = (
        max(0, int(x1 - 0.08 * bw)),
        max(0, int(y1 + top_frac * bh)),
        min(w, int(x2 + 0.08 * bw)),
        min(h, int(y1 + bot_frac * bh)),
    )
    crop = img.crop(box)
    if crop.width < 16 or crop.height < 6:
        return None
    return crop


def _bumper_crops(jpeg: bytes, dets: list[dict[str, Any]]) -> list[Image.Image]:
    img = Image.open(BytesIO(jpeg)).convert("RGB")
    crops: list[Image.Image] = []
    for det in _largest_vehicles(dets, img.size[1]):
        crop = _bumper_from_image(img, det)
        if crop is not None:
            crops.append(crop)
    return crops


def plate_crops(jpeg: bytes, dets: list[dict[str, Any]] | None = None) -> list[Image.Image]:
    """Tight plate boxes first; bumper band only if the detector finds nothing."""
    if not jpeg:
        return []
    img = Image.open(BytesIO(jpeg)).convert("RGB")
    w, h = img.size
    crops: list[Image.Image] = []
    for x1, y1, x2, y2, _conf in detect_plate_boxes(jpeg, dets):
        pad_x = 0.10 * max(1.0, x2 - x1)
        pad_y = 0.22 * max(1.0, y2 - y1)
        box = (
            max(0, int(x1 - pad_x)),
            max(0, int(y1 - pad_y)),
            min(w, int(x2 + pad_x)),
            min(h, int(y2 + pad_y)),
        )
        crop = img.crop(box)
        if crop.width >= 12 and crop.height >= 6:
            crops.append(crop)
    if crops:
        return crops
    return _bumper_crops(jpeg, dets or [])


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
    return np.median(np.stack(aligned), axis=0).astype(np.uint8)


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
    arr = np.array(enhance_low_res(crop).convert("RGB"))
    try:
        result = engine(arr, use_det=False, use_cls=False, use_rec=True)
    except TypeError:
        try:
            result = engine(arr)
        except Exception:
            log.exception("RapidOCR failed")
            return ""
    except Exception:
        log.exception("RapidOCR rec-only failed")
        return ""
    return " ".join(_parse_rapidocr(result))


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


def _ocr_crop(crop: Image.Image) -> str:
    return " ".join(part for part in (_ocr_rapid(crop), _ocr_tesseract(crop)) if part.strip())


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
    if not frames or not dets:
        return []
    images = [Image.open(BytesIO(frame)).convert("RGB") for frame in frames]
    h = images[-1].size[1]
    out: list[Image.Image] = []
    for det in _largest_vehicles(dets, h):
        grays: list[np.ndarray] = []
        for img in images:
            crop = _bumper_from_image(img, det)
            if crop is None:
                continue
            grays.append(np.asarray(crop.convert("L")))
        if not grays:
            continue
        fused = fuse_gray_crops(grays)
        sharp = grays[int(np.argmax([_sharpness(g) for g in grays]))]
        track_id = str(det.get("local_track_id") or "") or None
        out.append(_bank_fuse(camera_key, track_id, fused))
        out.append(enhance_low_res(Image.fromarray(sharp)))
    return out


def read_plate_text(
    jpeg: bytes,
    extra_crops: list[Image.Image] | None = None,
    *,
    frames: list[bytes] | None = None,
    dets: list[dict[str, Any]] | None = None,
    camera_key: str = "",
) -> str:
    """OCR plate / bumper crops only. Never run OCR on the full frame (OSD)."""
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
        if crop.width < 12 or crop.height < 6:
            continue
        text = _ocr_crop(crop)
        if text.strip():
            texts.append(text)
    return " ".join(texts)
