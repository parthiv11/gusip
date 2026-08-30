"""Per-camera ByteTrack-style association (high/low IoU, unmatched tracks)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _Track:
    track_id: int
    bbox: tuple[float, float, float, float]
    score: float
    misses: int = 0
    hits: int = 1


@dataclass
class CameraTracker:
    next_id: int = 1
    tracks: list[_Track] = field(default_factory=list)
    max_misses: int = 15
    high_iou: float = 0.5
    low_iou: float = 0.2

    def update(self, detections: list[dict]) -> list[dict]:
        boxes = [
            (
                det,
                (
                    float(det.get("x1", 0)),
                    float(det.get("y1", 0)),
                    float(det.get("x2", 0)),
                    float(det.get("y2", 0)),
                ),
                float(det.get("confidence") or 0),
            )
            for det in detections
        ]
        unmatched_tracks = set(range(len(self.tracks)))
        unmatched_dets = set(range(len(boxes)))

        for thresh in (self.high_iou, self.low_iou):
            pairs = []
            for ti in unmatched_tracks:
                for di in unmatched_dets:
                    iou = _iou(self.tracks[ti].bbox, boxes[di][1])
                    if iou >= thresh:
                        pairs.append((iou, ti, di))
            for _, ti, di in sorted(pairs, reverse=True):
                if ti not in unmatched_tracks or di not in unmatched_dets:
                    continue
                track = self.tracks[ti]
                _, bbox, score = boxes[di]
                track.bbox = bbox
                track.score = score
                track.misses = 0
                track.hits += 1
                boxes[di][0]["local_track_id"] = str(track.track_id)
                unmatched_tracks.discard(ti)
                unmatched_dets.discard(di)

        for ti in unmatched_tracks:
            self.tracks[ti].misses += 1
        self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]

        for di in unmatched_dets:
            det, bbox, score = boxes[di]
            track = _Track(track_id=self.next_id, bbox=bbox, score=score)
            self.next_id += 1
            self.tracks.append(track)
            det["local_track_id"] = str(track.track_id)
        return detections

    def reset(self) -> None:
        self.next_id = 1
        self.tracks = []


_cameras: dict[str, CameraTracker] = {}


def tracker_for(camera_key: str, stream_epoch: int | None = None) -> CameraTracker:
    key = f"{camera_key}:{stream_epoch if stream_epoch is not None else 0}"
    stale = [existing for existing in _cameras if existing.startswith(f"{camera_key}:") and existing != key]
    for existing in stale:
        _cameras.pop(existing, None)
    if key not in _cameras:
        _cameras[key] = CameraTracker()
    return _cameras[key]


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0
