"""ArcFace embeddings for watchlist match and search-by-photo.

Enroll, search, and live person crops use InsightFace ``buffalo_l``:
SCRFD detection + ``w600k_r50`` ArcFace (512-d, L2-normalized) via ONNX Runtime.

The ``insightface`` Python package is not used — it needs a C++ toolchain to
build on slim images. Weights are the same official pack.

Official Sentinel street feeds never run FRS. The simulator still emits a
deterministic canned vector so the laptop demo works without a face still.
"""

from __future__ import annotations

import hashlib
import logging
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from app.config import get_settings

log = logging.getLogger("gusip.face")

DIM = 512
MATCH_THRESHOLD = 0.42
MIN_CROP = 48
ARCFACE_DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)

_det: Any = None
_rec: Any = None
_det_meta: dict[str, Any] = {}
_failed = False
_fail_reason = ""
_center_cache: dict[tuple[int, int, int], np.ndarray] = {}


class FaceEngineError(Exception):
    """ArcFace weights are missing or failed to load."""


def l2_normalize(vec: np.ndarray) -> list[float]:
    arr = np.asarray(vec, dtype=np.float32).reshape(-1)
    if arr.size != DIM:
        if arr.size < DIM:
            arr = np.pad(arr, (0, DIM - arr.size))
        else:
            arr = arr[:DIM]
    n = float(np.linalg.norm(arr))
    if n <= 1e-8:
        return arr.tolist()
    return (arr / n).tolist()


def canned_embedding(tag: str) -> list[float]:
    """Stable mock ArcFace vector for simulator / seed (no still required)."""
    digest = hashlib.sha256(f"gusip-face:{tag}".encode()).digest()
    seed = int.from_bytes(digest[:8], "little") % (2**32)
    rng = np.random.default_rng(seed)
    return l2_normalize(rng.normal(0, 1, DIM))


def is_face_embedding(vec: list[float] | None) -> bool:
    """Appearance Re-ID hashes are 64-d; ArcFace vectors are 512-d."""
    return bool(vec) and len(vec) >= 256


def cosine_score(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    va = np.asarray(a, dtype=np.float32).reshape(-1)
    vb = np.asarray(b, dtype=np.float32).reshape(-1)
    n = min(va.size, vb.size)
    if n < 8:
        return 0.0
    va, vb = va[:n], vb[:n]
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na <= 1e-8 or nb <= 1e-8:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _settings():
    return get_settings()


def model_dir() -> Path:
    root = Path(_settings().face_model_root)
    return root / "models" / _settings().face_model


def arcface_ready() -> bool:
    return _det is not None and _rec is not None


def arcface_status() -> dict[str, Any]:
    return {
        "engine": "arcface",
        "model": _settings().face_model,
        "ready": arcface_ready(),
        "error": _fail_reason or None,
    }


def _download_buffalo() -> None:
    dest = model_dir()
    dest.mkdir(parents=True, exist_ok=True)
    det = dest / "det_10g.onnx"
    rec = dest / "w600k_r50.onnx"
    if det.exists() and rec.exists():
        return
    url = _settings().face_pack_url
    log.info("Downloading ArcFace pack %s", url)
    raw = urlopen(url, timeout=180).read()  # noqa: S310 — configured model URL
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        for member in zf.namelist():
            name = Path(member).name
            if name in {"det_10g.onnx", "w600k_r50.onnx"}:
                (dest / name).write_bytes(zf.read(member))
    if not det.exists() or not rec.exists():
        raise FileNotFoundError("buffalo_l zip did not contain det_10g.onnx / w600k_r50.onnx")


def _nms(dets: np.ndarray, thresh: float) -> list[int]:
    if dets.size == 0:
        return []
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        ovr = w * h / (areas[i] + areas[order[1:]] - w * h + 1e-8)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return keep


def _distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def _distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, 0] + distance[:, i]
        py = points[:, 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


def _load_sessions() -> None:
    global _det, _rec, _det_meta, _failed, _fail_reason
    if _det is not None and _rec is not None:
        return
    if _failed:
        raise FaceEngineError(_fail_reason or "ArcFace failed to load")
    try:
        import onnxruntime as ort

        _download_buffalo()
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        providers = ["CPUExecutionProvider"]
        det_path = str(model_dir() / "det_10g.onnx")
        rec_path = str(model_dir() / "w600k_r50.onnx")
        _det = ort.InferenceSession(det_path, so, providers=providers)
        _rec = ort.InferenceSession(rec_path, so, providers=providers)
        outputs = _det.get_outputs()
        _det_meta = {
            "input": _det.get_inputs()[0].name,
            "outputs": [o.name for o in outputs],
            "fmc": 3 if len(outputs) in {6, 9} else 5,
            "strides": [8, 16, 32] if len(outputs) in {6, 9} else [8, 16, 32, 64, 128],
            "num_anchors": 2 if len(outputs) in {6, 9} else 1,
            "use_kps": len(outputs) in {9, 15},
        }
        log.info("ArcFace buffalo_l ready (SCRFD + w600k_r50 CPU)")
    except FaceEngineError:
        raise
    except Exception as exc:
        _failed = True
        _fail_reason = f"ArcFace failed to load: {exc}"
        log.exception("ArcFace load failed")
        raise FaceEngineError(_fail_reason) from exc


def warmup_arcface() -> bool:
    """Download weights and load ONNX sessions. Safe to call from a worker thread."""
    if not _settings().face_enabled:
        return False
    try:
        _load_sessions()
        return True
    except FaceEngineError:
        return False


def require_arcface() -> None:
    if not _settings().face_enabled:
        raise FaceEngineError("Face engine is disabled")
    _load_sessions()


def _detect_bgr(bgr: np.ndarray, threshold: float | None = None) -> list[dict[str, Any]]:
    require_arcface()
    import cv2

    thresh = float(threshold if threshold is not None else _settings().face_min_det_score)
    size = int(_settings().face_det_size)
    im_h, im_w = bgr.shape[:2]
    im_ratio = im_h / max(im_w, 1)
    if im_ratio > 1:
        new_h = size
        new_w = max(1, int(new_h / im_ratio))
    else:
        new_w = size
        new_h = max(1, int(new_w * im_ratio))
    det_scale = new_h / max(im_h, 1)
    resized = cv2.resize(bgr, (new_w, new_h))
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    canvas[:new_h, :new_w] = resized
    blob = cv2.dnn.blobFromImage(
        canvas,
        1.0 / 128.0,
        (size, size),
        (127.5, 127.5, 127.5),
        swapRB=True,
    )
    net_outs = _det.run(_det_meta["outputs"], {_det_meta["input"]: blob})
    fmc = int(_det_meta["fmc"])
    scores_all: list[np.ndarray] = []
    boxes_all: list[np.ndarray] = []
    kps_all: list[np.ndarray] = []
    for idx, stride in enumerate(_det_meta["strides"]):
        scores = net_outs[idx].reshape(-1)
        bbox_preds = net_outs[idx + fmc].reshape(-1, 4) * stride
        height = size // stride
        width = size // stride
        key = (height, width, stride)
        centers = _center_cache.get(key)
        if centers is None:
            centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
            centers = (centers * stride).reshape((-1, 2))
            anchors = int(_det_meta["num_anchors"])
            if anchors > 1:
                centers = np.stack([centers] * anchors, axis=1).reshape((-1, 2))
            _center_cache[key] = centers
        pos = np.where(scores >= thresh)[0]
        if pos.size == 0:
            continue
        boxes = _distance2bbox(centers, bbox_preds)[pos]
        scores_all.append(scores[pos])
        boxes_all.append(boxes)
        if _det_meta["use_kps"]:
            kps = _distance2kps(centers, net_outs[idx + fmc * 2].reshape(-1, 10) * stride)
            kps = kps.reshape((kps.shape[0], -1, 2))
            kps_all.append(kps[pos])
    if not scores_all:
        return []
    scores_c = np.concatenate(scores_all, axis=0)
    boxes_c = np.concatenate(boxes_all, axis=0) / det_scale
    dets = np.hstack([boxes_c, scores_c[:, None]])
    keep = _nms(dets, 0.4)
    faces: list[dict[str, Any]] = []
    kps_c = np.concatenate(kps_all, axis=0) / det_scale if kps_all else None
    for i in keep:
        item = {
            "bbox": dets[i, :4].tolist(),
            "det_score": float(dets[i, 4]),
        }
        if kps_c is not None:
            item["kps"] = kps_c[i]
        faces.append(item)
    faces.sort(key=lambda f: f["det_score"], reverse=True)
    return faces


def _align(bgr: np.ndarray, kps: np.ndarray | None, bbox: list[float]) -> np.ndarray:
    import cv2

    if kps is not None and np.asarray(kps).size >= 10:
        src = np.asarray(kps, dtype=np.float32).reshape(-1, 2)[:5]
        matrix, _ = cv2.estimateAffinePartial2D(src, ARCFACE_DST, method=cv2.LMEDS)
        if matrix is not None:
            return cv2.warpAffine(bgr, matrix, (112, 112), borderValue=0.0)
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(bgr.shape[1], x2), min(bgr.shape[0], y2)
    crop = bgr[y1:y2, x1:x2]
    if crop.size == 0:
        crop = bgr
    return cv2.resize(crop, (112, 112))


def _embed_aligned(aligned_bgr: np.ndarray) -> list[float]:
    require_arcface()
    blob = aligned_bgr.astype(np.float32)
    blob = (blob - 127.5) / 127.5
    blob = blob[:, :, ::-1]  # BGR → RGB, InsightFace w600k convention
    blob = np.transpose(blob, (2, 0, 1))[None, ...]
    name = _rec.get_inputs()[0].name
    out = _rec.run(None, {name: blob})[0]
    return l2_normalize(out)


def _image_to_bgr(jpeg: bytes) -> np.ndarray:
    img = Image.open(BytesIO(jpeg))
    img = ImageOps.exif_transpose(img).convert("RGB")
    rgb = np.asarray(img)
    return rgb[:, :, ::-1].copy()


def detect_faces(jpeg: bytes) -> list[dict[str, Any]]:
    return _detect_bgr(_image_to_bgr(jpeg))


def embed_image_bytes(jpeg: bytes) -> tuple[list[float], dict[str, Any]] | None:
    """ArcFace embedding of the strongest face in a still. None if no face."""
    require_arcface()
    if not jpeg:
        return None
    bgr = _image_to_bgr(jpeg)
    faces = _detect_bgr(bgr)
    if not faces:
        return None
    face = faces[0]
    aligned = _align(bgr, face.get("kps"), face["bbox"])
    vec = _embed_aligned(aligned)
    return vec, {
        "engine": "arcface",
        "model": "w600k_r50",
        "det_score": face["det_score"],
        "faces": len(faces),
    }


def embed_person_in_frame(jpeg: bytes, det: dict[str, Any]) -> tuple[list[float], dict[str, Any]] | None:
    """ArcFace on the face that sits inside a YOLO person box."""
    require_arcface()
    bgr = _image_to_bgr(jpeg)
    h, w = bgr.shape[:2]
    px1, py1, px2, py2 = _person_xyxy(det, w, h)
    faces = _detect_bgr(bgr)
    chosen = None
    for face in faces:
        x1, y1, x2, y2 = face["bbox"]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if px1 <= cx <= px2 and py1 <= cy <= py2:
            chosen = face
            break
    if chosen is None:
        crop = person_crop(jpeg, det)
        if crop is None:
            return None
        buf = BytesIO()
        crop.save(buf, format="JPEG", quality=90)
        return embed_image_bytes(buf.getvalue())
    aligned = _align(bgr, chosen.get("kps"), chosen["bbox"])
    vec = _embed_aligned(aligned)
    return vec, {
        "engine": "arcface",
        "model": "w600k_r50",
        "det_score": chosen["det_score"],
        "faces": len(faces),
        "yaw": None,
    }


def _person_xyxy(det: dict[str, Any], w: int, h: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = det.get("x1"), det.get("y1"), det.get("x2"), det.get("y2")
    if None not in (x1, y1, x2, y2):
        return float(x1), float(y1), float(x2), float(y2)
    bbox = det.get("bbox") or {}
    fw, fh = float(det.get("frame_w") or w), float(det.get("frame_h") or h)
    x1 = float(bbox.get("x", 0)) / 400 * fw
    y1 = float(bbox.get("y", 0)) / 240 * fh
    x2 = x1 + float(bbox.get("w", 0)) / 400 * fw
    y2 = y1 + float(bbox.get("h", 0)) / 240 * fh
    return x1, y1, x2, y2


def crop_quality_ok(crop: Image.Image) -> tuple[bool, dict[str, Any]]:
    w, h = crop.size
    if min(w, h) < MIN_CROP:
        return False, {"reason": "too_small", "w": w, "h": h}
    gray = np.asarray(crop.convert("L"), dtype=np.float32)
    blur = float(gray.var())
    if blur < 18:
        return False, {"reason": "blur", "blur": blur}
    return True, {"blur": blur, "w": w, "h": h}


def person_crop(jpeg: bytes, det: dict[str, Any]) -> Image.Image | None:
    img = Image.open(BytesIO(jpeg)).convert("RGB")
    w, h = img.size
    x1, y1, x2, y2 = _person_xyxy(det, w, h)
    bw, bh = max(1.0, float(x2) - float(x1)), max(1.0, float(y2) - float(y1))
    box = (
        max(0, int(float(x1) - 0.08 * bw)),
        max(0, int(float(y1) - 0.04 * bh)),
        min(w, int(float(x2) + 0.08 * bw)),
        min(h, int(float(y1) + 0.48 * bh)),
    )
    crop = img.crop(box)
    if crop.width < 16 or crop.height < 16:
        return None
    return crop.filter(ImageFilter.SHARPEN)


def should_run_live_face(source_type: str | None) -> bool:
    """Never run FRS on official Sentinel public street feeds."""
    return (source_type or "") != "sentinel"
