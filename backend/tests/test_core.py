from types import SimpleNamespace

from app.core.plates import format_plate, normalize_plate
from app.core.policy import capabilities_for, has_capability, is_home_scoped, validate_purpose
from app.models.watchlist import WatchlistEntry
from app.services.anpr import extract_plates
from app.services.matching import alert_fingerprint, match_entry
from app.services.tracking import appearance_embedding, cosine
from fastapi import HTTPException


def test_normalize_indian_plates():
    assert normalize_plate("GJ-01-AB-1234") == "GJ01AB1234"
    assert normalize_plate("gj 01 ab 1234") == "GJ01AB1234"
    assert format_plate("GJ01AB1234") == "GJ 01 AB 1234"
    assert format_plate("22BH1234AB").startswith("22 BH")


def test_extract_plates_from_noisy_ocr():
    plates = extract_plates("noise GJ01AB1234 camera Paldi")
    norms = {p.replace(" ", "") for p, _ in plates}
    assert "GJ01AB1234" in norms


def test_watchlist_exact_and_partial():
    entry = WatchlistEntry(
        entity_type="vehicle",
        category="stolen_vehicle",
        plate_normalized="GJ01ST0001",
        name="Fortuner",
        extra={},
    )
    ok, conf = match_entry(entry, "GJ01ST0001", {})
    assert ok and conf > 0.9
    ok2, conf2 = match_entry(entry, "GJ01XX0001", {})
    assert ok2 and conf2 < 0.9
    no, _ = match_entry(entry, "MH12AB1234", {})
    assert not no


def test_reid_embedding_stable_for_same_appearance():
    a = appearance_embedding({"color": "white", "vehicle_class": "suv", "make": "Toyota"})
    b = appearance_embedding({"color": "white", "vehicle_class": "suv", "make": "Toyota"})
    c = appearance_embedding({"color": "black", "vehicle_class": "sedan", "make": "Honda"})
    assert cosine(a, b) > 0.99
    assert cosine(a, c) < 0.85


def test_operator_cannot_export_but_can_search():
    op = SimpleNamespace(role="control_room_operator", department_id=1)
    assert has_capability(op, "search")
    assert has_capability(op, "ack_alert")
    assert not has_capability(op, "export")
    assert not has_capability(op, "watchlist_write")
    assert not is_home_scoped(op)


def test_investigator_can_export():
    io = SimpleNamespace(role="investigation_officer", department_id=1)
    assert has_capability(io, "export")
    assert has_capability(io, "watchlist_write")
    assert "export" in capabilities_for("investigation_officer")


def test_coordinator_is_home_scoped():
    coord = SimpleNamespace(role="department_coordinator", department_id=3)
    assert is_home_scoped(coord)
    assert has_capability(coord, "break_glass")
    assert has_capability(coord, "export")


def test_purpose_required():
    assert validate_purpose("stolen_vehicle") == "stolen_vehicle"
    try:
        validate_purpose("")
        assert False, "empty purpose should fail"
    except HTTPException as exc:
        assert exc.status_code == 400
    try:
        validate_purpose("curiosity")
        assert False, "unknown purpose should fail"
    except HTTPException as exc:
        assert exc.status_code == 400


def test_alert_fingerprint_is_camera_and_watchlist():
    assert alert_fingerprint(4, 12) == "4:12"
    assert alert_fingerprint(4, 12) != alert_fingerprint(4, 13)


def test_sentinel_ingest_catalogue_shape():
    from app.workers.sentinel import grab_cmd, inference_url, normalize_camera

    row = normalize_camera(
        {
            "id": "1",
            "name": "Camera 1",
            "location": "01 Chiman bhai Bridge",
            "codec": "hevc",
            "live": True,
            "rtsp_url": "rtsp://live.corp8.cloud:8554/stream/1",
            "webrtc_url": "http://live.corp8.cloud:8889/stream/1/whep",
            "hls_live_url": "/live/stream/1/index.m3u8",
        },
        base_url="https://live.corp8.cloud",
    )
    assert row["id"] == "1"
    assert row["live"] is True
    assert row["rtsp_url"].startswith("rtsp://")
    assert row["whep_url"].endswith("/whep")
    assert row["hls_url"] == "https://live.corp8.cloud/live/stream/1/index.m3u8"
    assert row["stream_url"].endswith("/stream/1")
    assert inference_url(row) == row["rtsp_url"]
    assert inference_url({"hls_url": row["hls_url"], "stream_url": row["stream_url"]}) == row["hls_url"]
    assert inference_url({"stream_url": row["stream_url"]}) is None

    cmd = grab_cmd(row["rtsp_url"])
    assert "-rtsp_transport" in cmd and "tcp" in cmd
    assert "-ss" not in cmd
    hls_cmd = grab_cmd(row["hls_url"])
    assert "-user_agent" in hls_cmd
    assert "-rtsp_transport" not in hls_cmd
    from app.workers.sentinel import _playlist_refs

    refs = _playlist_refs("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nstream.m3u8\n", "https://live.corp8.cloud/live/stream/1/index.m3u8?cookieCheck=1")
    assert refs == ["https://live.corp8.cloud/live/stream/1/stream.m3u8?cookieCheck=1"]
    offline = normalize_camera({"id": "9", "status": "offline", "live": False})
    assert offline["live"] is False
    assert "8554/stream/9" in offline["rtsp_url"]


def test_canned_face_embedding_stable_and_distinct():
    from app.services.face import canned_embedding, cosine_score

    a = canned_embedding("wanted-rakesh")
    b = canned_embedding("wanted-rakesh")
    other = canned_embedding("wanted-kiran")
    assert len(a) == 512
    assert cosine_score(a, b) > 0.99
    assert cosine_score(a, other) < 0.4


def test_person_match_uses_face_embedding():
    from app.services.face import MATCH_THRESHOLD, canned_embedding

    vec = canned_embedding("wanted-rakesh")
    entry = WatchlistEntry(
        entity_type="person",
        category="wanted_person",
        name="Rakesh M.",
        appearance_notes="",
        extra={"sim_tag": "wanted-rakesh"},
        face_embedding=vec,
    )
    ok, conf = match_entry(entry, None, {}, embedding=vec)
    assert ok and conf >= MATCH_THRESHOLD
    no, _ = match_entry(entry, None, {}, embedding=canned_embedding("wanted-kiran"))
    assert not no


def test_person_clothing_fallback_without_face_vector():
    entry = WatchlistEntry(
        entity_type="person",
        category="wanted_person",
        name="Rakesh M.",
        appearance_notes="grey hoodie",
        extra={"sim_tag": "wanted-rakesh"},
        face_embedding=None,
    )
    ok, conf = match_entry(entry, None, {"clothing": "grey hoodie"})
    assert ok and conf == 0.72
    tagged, tconf = match_entry(entry, None, {"watch_tag": "wanted-rakesh"})
    assert tagged and tconf == 0.88


def test_live_face_skips_sentinel_street_feeds():
    from app.services.face import should_run_live_face

    assert should_run_live_face("sentinel") is False
    assert should_run_live_face("rtsp") is True
    assert should_run_live_face("onvif") is True


def test_arcface_status_reports_engine():
    from app.services.face import arcface_status

    status = arcface_status()
    assert status["engine"] == "arcface"
    assert status["model"] == "buffalo_l"
    assert "ready" in status
