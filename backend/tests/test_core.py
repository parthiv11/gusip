from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
import json
import time

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from app.config import Settings
from app.core.plates import format_plate, normalize_plate
from app.core.policy import capabilities_for, has_capability, is_home_scoped, validate_purpose
from app.models.watchlist import WatchlistEntry
from app.schemas.ingest import DetectionEnvelope
from app.services.anpr import extract_plates
from app.services.matching import alert_fingerprint, match_entry
from app.services.tracking import appearance_embedding, cosine
from fastapi import HTTPException


def test_production_settings_reject_poc_defaults():
    with pytest.raises(ValidationError, match="unsafe production configuration"):
        Settings(app_env="production", _env_file=None)


def test_production_settings_accept_explicit_secure_values():
    settings = Settings(
        app_env="production",
        secret_key="s" * 64,
        encryption_key="e" * 64,
        session_cookie_secure=True,
        local_auth_enabled=False,
        auth_provider="oidc",
        oidc_issuer="https://id.example.in/realms/gusip",
        oidc_jwks_url="https://id.example.in/realms/gusip/protocol/openid-connect/certs",
        oidc_authorization_url="https://id.example.in/realms/gusip/protocol/openid-connect/auth",
        oidc_token_url="https://id.example.in/realms/gusip/protocol/openid-connect/token",
        audit_enabled=True,
        simulation_enabled=False,
        minio_secure=True,
        minio_access_key="prod-object-user",
        minio_secret_key="m" * 40,
        cors_origins="https://gusip.example.in",
        adapter_keys_json='{"dept-a":"' + ("a" * 40) + '"}',
        _env_file=None,
    )
    assert settings.cors_origin_list == ["https://gusip.example.in"]


async def test_oidc_login_uses_pkce_and_transient_http_only_cookies():
    from app.api import auth

    old_provider = auth.settings.auth_provider
    old_url = auth.settings.oidc_authorization_url
    old_secure = auth.settings.session_cookie_secure
    auth.settings.auth_provider = "oidc"
    auth.settings.oidc_authorization_url = "https://id.example.in/realms/gusip/protocol/openid-connect/auth"
    auth.settings.session_cookie_secure = True
    try:
        response = await auth.oidc_login()
    finally:
        auth.settings.auth_provider = old_provider
        auth.settings.oidc_authorization_url = old_url
        auth.settings.session_cookie_secure = old_secure
    assert response.status_code == 302
    assert "code_challenge_method=S256" in response.headers["location"]
    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 3
    assert all("HttpOnly" in cookie and "Secure" in cookie for cookie in cookies)


async def test_oidc_token_decode_via_jwks_rs256():
    """Covers the PyJWT/PyJWK RS256 path in core.security.decode_access_token —
    migrated off python-jose (unmaintained, multiple unfixed CVEs including one
    via its ecdsa dependency); this path had no direct test before."""
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.core import security

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(pyjwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "test-kid", "use": "sig", "kty": "RSA"})

    old_provider = security.settings.auth_provider
    old_audience = security.settings.oidc_audience
    old_issuer = security.settings.oidc_issuer
    security.settings.auth_provider = "oidc"
    security.settings.oidc_audience = "gusip"
    security.settings.oidc_issuer = "https://id.example.in/realms/gusip"
    security._jwks_cache = (time.monotonic() + 300, {"keys": [public_jwk]})
    try:
        token = pyjwt.encode(
            {"sub": "12345", "role": "control_room_operator", "aud": "gusip", "iss": "https://id.example.in/realms/gusip"},
            private_key,
            algorithm="RS256",
            headers={"kid": "test-kid"},
        )
        claims = await security.decode_access_token(token)
        assert claims["sub"] == "12345"

        with pytest.raises(security.JWTError):
            await security.decode_access_token(token + "tampered")
    finally:
        security.settings.auth_provider = old_provider
        security.settings.oidc_audience = old_audience
        security.settings.oidc_issuer = old_issuer
        security._jwks_cache = None


def test_ingest_envelope_forbids_adapter_media_urls():
    payload = {
        "adapter_id": "dept-a",
        "event_id": str(uuid4()),
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "sequence": 1,
        "schema_version": "1.0",
        "payload": {
            "camera_id": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "snapshot_url": "https://attacker.example/token",
        },
    }
    with pytest.raises(ValidationError, match="snapshot_url"):
        DetectionEnvelope.model_validate(payload)


def test_sentinel_allowlist_includes_cctv_redirect_host(monkeypatch):
    from app.config import Settings
    from app.workers import sentinel as sen

    default_hosts = Settings.model_fields["sentinel_allowed_hosts"].default
    assert "cctv.corp8.cloud" in default_hosts
    fresh = Settings(_env_file=None, sentinel_allowed_hosts=default_hosts)
    monkeypatch.setattr(sen, "settings", fresh)
    assert sen.validate_sentinel_url("https://cctv.corp8.cloud/stream/1") == "https://cctv.corp8.cloud/stream/1"


def test_grid_cameras_json_builds_contract_urls(monkeypatch):
    from app.config import Settings
    from app.services import sentinel_auth
    from app.workers import sentinel as sen

    fresh = Settings(
        _env_file=None,
        sentinel_base_url="https://cctv.corp8.cloud",
        sentinel_email="alice@example.com",
        sentinel_password="GRID-KEY",
        sentinel_rtsp_host="103.250.160.189",
        sentinel_allowed_hosts="cctv.corp8.cloud,103.250.160.189",
    )
    monkeypatch.setattr(sen, "settings", fresh)
    monkeypatch.setattr(sentinel_auth, "get_settings", lambda: fresh)
    row = sen.normalize_camera({"id": "cam04", "name": "04 Test"}, base_url="https://cctv.corp8.cloud")
    assert row["id"] == "cam04"
    assert row["live"] is True
    assert row["hls_url"] == "https://cctv.corp8.cloud/cam04/index.m3u8"
    assert row["rtsp_url"] == "rtsp://alice%40example.com:GRID-KEY@103.250.160.189:8554/stream/cam04"
    assert row["whep_url"] == "http://alice%40example.com:GRID-KEY@103.250.160.189:8889/stream/cam04/whep"
    sen.validate_sentinel_url(row["rtsp_url"], frozenset({"rtsp"}))


def test_still_loop_requires_preview_jpeg(tmp_path, monkeypatch):
    from app.services import local_feed

    monkeypatch.setattr(local_feed, "PREVIEW_DIR", tmp_path)
    monkeypatch.setattr(local_feed, "LOOP_DIR", tmp_path / "loops")
    assert local_feed.ensure_still_loop("1") is None


def test_sentinel_catalogue_redacts_upstream_media_urls():
    from app.api.feeds import _public_catalogue_camera

    public = _public_catalogue_camera(
        {
            "id": "1",
            "name": "Camera 1",
            "codec": "h264",
            "rtsp_url": "rtsp://upstream:8554/stream/1",
            "hls_url": "https://upstream/live/stream/1/index.m3u8",
            "whep_url": "http://upstream:8889/stream/1/whep",
        }
    )
    assert public == {"id": "1", "name": "Camera 1", "codec": "h264"}


def test_normalize_indian_plates():
    assert normalize_plate("GJ-01-AB-1234") == "GJ01AB1234"
    assert normalize_plate("gj 01 ab 1234") == "GJ01AB1234"
    assert format_plate("GJ01AB1234") == "GJ 01 AB 1234"
    assert format_plate("22BH1234AB").startswith("22 BH")


def test_extract_plates_from_noisy_ocr():
    plates = extract_plates("noise GJ01AB1234 camera Paldi")
    norms = {p.replace(" ", "") for p, _ in plates}
    assert "GJ01AB1234" in norms


def test_extract_plates_ignores_osd_timestamps():
    from app.services.anpr import extract_plates

    assert extract_plates("14-06-2026 05:04:02 Suvidhapark P3 RLVD CSITMS32PTZ") == []
    assert extract_plates("ES 4A N2 026 P1RLVD 062026044255") == []
    assert extract_plates("ST 4M WT 4062 bilimora overlay") == []
    plates = extract_plates("hit GJ 01 ST 0001 overlay 14-06-2026 CSITMS")
    norms = {p.replace(" ", "") for p, _ in plates}
    assert "GJ01ST0001" in norms


def test_vote_ocr_recovers_plate_from_noisy_reads():
    from app.services.anpr import vote_ocr_strings

    voted = vote_ocr_strings(["GJ0IAB1234", "GJ01AB1234", "GJ01AB12B4"])
    assert voted == "GJ01AB1234"


def test_enhance_and_fuse_low_res_crops():
    from app.services.plate_ocr import enhance_low_res, fuse_gray_crops

    tiny = Image.new("L", (22, 8), 80)
    big = enhance_low_res(tiny)
    assert big.height >= 48
    assert big.width >= 192
    a = np.full((20, 60), 40, dtype=np.uint8)
    a[8:12, 10:50] = 200
    b = np.roll(a, 1, axis=1)
    fused = fuse_gray_crops([a, b, a])
    assert fused.shape[0] >= 8 and fused.shape[1] >= 16


def test_plate_box_rejects_square_glare():
    from app.services.plate_ocr import _looks_like_indian_plate

    assert not _looks_like_indian_plate(0, 0, 20, 19, 1080)
    assert not _looks_like_indian_plate(10, 10, 80, 70, 1080)
    assert not _looks_like_indian_plate(0, 700, 327, 794, 1080)
    assert _looks_like_indian_plate(400, 800, 490, 828, 1080)


def test_read_plate_text_skips_empty_crops():
    from app.services.plate_ocr import read_plate_text

    assert read_plate_text(b"", []) == ""
    tiny = Image.new("L", (16, 8), 180)
    assert read_plate_text(b"", extra_crops=[tiny]) == ""


def test_ocrable_crop_rejects_bumper_and_cjk():
    from app.services.plate_ocr import (
        _contour_plate_xyxy,
        _is_ocrable_plate_crop,
        _latin_ocr_keep,
    )

    assert not _is_ocrable_plate_crop(Image.new("RGB", (824, 122), 180))
    assert not _is_ocrable_plate_crop(Image.new("RGB", (16, 8), 180))
    assert _is_ocrable_plate_crop(Image.new("RGB", (71, 33), 180))
    assert _latin_ocr_keep("一 一") == ""
    assert _latin_ocr_keep("1 S SS SS") == ""
    assert "山" not in _latin_ocr_keep("M 山 P 1 1 B J")
    assert _latin_ocr_keep("GJ 01 ST 0001") == "GJ 01 ST 0001"
    bumper = np.full((80, 240, 3), 18, dtype=np.uint8)
    bumper[28:48, 70:190] = 230
    boxes = _contour_plate_xyxy(bumper)
    assert boxes
    w = boxes[0][2] - boxes[0][0]
    h = boxes[0][3] - boxes[0][1]
    assert 80 <= w <= 140 and 12 <= h <= 36


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


def test_watchlist_appearance_when_plate_unreadable():
    from app.services.matching import match_entry
    from app.services.scene import analyze_scene
    from app.services.vision_attrs import class_compatible, estimate_color, is_close_vehicle

    entry = WatchlistEntry(
        entity_type="vehicle",
        category="stolen_vehicle",
        plate_normalized="GJ01ST0001",
        name="Fortuner",
        extra={"color": "white", "vehicle_class": "suv"},
    )
    miss, _ = match_entry(entry, None, {"color": "white", "vehicle_class": "car", "close": False})
    assert not miss
    ok, conf = match_entry(entry, None, {"color": "white", "vehicle_class": "car", "close": True})
    assert ok and 0.7 <= conf < 0.9
    no, _ = match_entry(entry, None, {"color": "yellow", "vehicle_class": "car", "close": True})
    assert not no
    crowd = analyze_scene([{"object_type": "person"}] * 6)
    assert any(s["event_type"] == "crowding" for s in crowd)
    assert class_compatible("suv", "car")
    assert not class_compatible("suv", "bus")
    img = Image.new("RGB", (80, 50), (230, 230, 228))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    jpeg = buf.getvalue()
    det = {"x1": 0, "y1": 0, "x2": 80, "y2": 50, "object_type": "vehicle", "frame_h": 50}
    assert estimate_color(jpeg, det) == "white"
    det_far = {"object_type": "vehicle", "x1": 0, "y1": 0, "x2": 40, "y2": 20, "frame_h": 1080}
    assert not is_close_vehicle(det_far)


def test_coalesce_consecutive_same_camera_hops():
    from app.services.tracking import coalesce_consecutive_camera_hops

    pts = [
        SimpleNamespace(camera_id=1, t=1),
        SimpleNamespace(camera_id=1, t=2),
        SimpleNamespace(camera_id=1, t=3),
        SimpleNamespace(camera_id=2, t=4),
        SimpleNamespace(camera_id=2, t=5),
        SimpleNamespace(camera_id=1, t=6),
    ]
    hops = coalesce_consecutive_camera_hops(pts)
    assert [p.camera_id for p in hops] == [1, 2, 1]
    assert hops[0].t == 3
    assert hops[1].t == 5
    assert hops[2].t == 6


def test_decorate_track_counts_dwell_hits():
    from app.api.search import _decorate_track_points

    ts = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)

    def pt(i, cam, minute):
        return SimpleNamespace(
            id=i,
            global_track_id="veh-GJ01ST0001",
            camera_id=cam,
            timestamp=ts.replace(minute=minute),
            latitude=23.0 + cam * 0.01,
            longitude=72.5,
            object_type="vehicle",
            plate_normalized="GJ01ST0001",
            confidence=0.9,
            camera=SimpleNamespace(code=f"CAM-{cam}", name="Road", city="Ahmedabad"),
        )

    hops = _decorate_track_points(
        [pt(1, 1, 0), pt(2, 1, 1), pt(3, 2, 2), pt(4, 2, 3), pt(5, 1, 4), pt(6, 3, 5)]
    )
    assert [h.camera_id for h in hops] == [1, 2, 3]
    assert hops[0].hits == 3
    assert hops[1].hits == 2
    assert hops[2].hits == 1
    assert hops[0].first_seen == ts.replace(minute=0)
    assert hops[0].timestamp == ts.replace(minute=4)
    assert hops[0].camera_code == "CAM-1"

    a = appearance_embedding({"color": "white", "vehicle_class": "suv", "make": "Toyota"})
    b = appearance_embedding({"color": "white", "vehicle_class": "suv", "make": "Toyota"})
    c = appearance_embedding({"color": "black", "vehicle_class": "sedan", "make": "Honda"})
    assert cosine(a, b) > 0.99
    assert cosine(a, c) < 0.85


async def test_stream_epoch_resets_tracking_without_history_lookup():
    from app.services.tracking import resolve_global_track

    first = await resolve_global_track(
        None,
        camera_id=7,
        object_type="vehicle",
        plate_normalized="GJ01AB1234",
        embedding=None,
        timestamp=datetime.now(timezone.utc),
        stream_epoch=1,
    )
    second = await resolve_global_track(
        None,
        camera_id=7,
        object_type="vehicle",
        plate_normalized="GJ01AB1234",
        embedding=None,
        timestamp=datetime.now(timezone.utc),
        stream_epoch=2,
    )
    assert first != second


def test_operator_cannot_export_but_can_search():
    op = SimpleNamespace(role="control_room_operator", department_id=1)
    assert has_capability(op, "search")
    assert has_capability(op, "ack_alert")
    assert not has_capability(op, "export")
    assert not has_capability(op, "watchlist_write")
    assert is_home_scoped(op)


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


def test_system_admin_is_super_admin():
    admin = SimpleNamespace(role="system_admin", department_id=None)
    assert has_capability(admin, "manage_roles")
    assert has_capability(admin, "create_user")
    assert "manage_roles" in capabilities_for("system_admin")
    assert not is_home_scoped(admin)


def test_custom_role_strips_privileged_caps_and_stays_home_scoped():
    from app.core.policy import register_custom_roles, sanitize_caps

    class Row:
        slug = "night_lead"
        name = "Night lead"
        capabilities = ["view_live", "ack_alert", "manage_roles", "create_user"]
        statewide = False

    register_custom_roles([Row()])
    try:
        assert "manage_roles" not in sanitize_caps(["view_live", "manage_roles"])
        assert "view_live" in capabilities_for("night_lead")
        assert "manage_roles" not in capabilities_for("night_lead")
        user = SimpleNamespace(role="night_lead", department_id=1)
        assert has_capability(user, "ack_alert")
        assert not has_capability(user, "manage_roles")
        assert is_home_scoped(user)
    finally:
        register_custom_roles([])


def test_custom_statewide_role_is_not_home_scoped():
    from app.core.policy import register_custom_roles

    class Row:
        slug = "state_desk"
        name = "State desk"
        capabilities = ["search", "export"]
        statewide = True

    register_custom_roles([Row()])
    try:
        user = SimpleNamespace(role="state_desk", department_id=2)
        assert "statewide" in capabilities_for("state_desk")
        assert not is_home_scoped(user)
    finally:
        register_custom_roles([])


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
    assert row["stream_url"].endswith("/1/index.m3u8")
    assert inference_url(row) == row["rtsp_url"]
    assert inference_url({"hls_url": row["hls_url"], "stream_url": row["stream_url"]}) == row["hls_url"]
    assert inference_url({"stream_url": row["stream_url"]}) is None

    from app.workers import sentinel as sen

    sen.settings.sentinel_rtsp_enabled = False
    try:
        assert inference_url(row) == row["hls_url"]
    finally:
        sen.settings.sentinel_rtsp_enabled = True
    sen._mark_rtsp_success()
    assert inference_url(row) == row["rtsp_url"]
    sen._mark_rtsp_failure(now=time.monotonic())
    assert inference_url(row) == row["hls_url"]
    sen._mark_rtsp_success()
    assert sen._mark_rtsp_failure(now=100.0) == 2.0
    assert not sen._rtsp_available(now=101.9)
    assert sen._rtsp_available(now=102.0)
    assert [sen._mark_rtsp_failure(now=100.0) for _ in range(5)][-1] == 30.0
    sen._mark_rtsp_success()

    cmd = grab_cmd(row["rtsp_url"])
    assert "-rtsp_transport" in cmd and "tcp" in cmd
    assert "-ss" not in cmd
    assert "-vf" not in cmd
    assert "-copyts" in cmd and "-progress" in cmd
    hls_cmd = grab_cmd(row["hls_url"])
    assert "-user_agent" in hls_cmd
    assert "-rtsp_transport" not in hls_cmd
    hls_headers = " ".join(hls_cmd)
    assert "Referer: https://live.corp8.cloud/camera/1" in hls_headers
    assert "Origin: https://live.corp8.cloud" in hls_headers
    from app.workers.sentinel import (
        _hls_player_headers,
        _parse_progress_pts,
        _playlist_refs,
        advance_stream_clock,
        rewrite_hls_location,
        validate_sentinel_url,
    )

    refs = _playlist_refs(
        "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nstream.m3u8\n",
        "https://live.corp8.cloud/live/stream/1/index.m3u8?cookieCheck=1",
        session="abc-uuid",
    )
    assert refs == ["https://live.corp8.cloud/live/stream/1/stream.m3u8?session=abc-uuid"]
    assert rewrite_hls_location(
        "https://live.corp8.cloud/live/stream/1/index.m3u8",
        "/stream/1/index.m3u8?cookieCheck=1",
    ) == "https://live.corp8.cloud/live/stream/1/index.m3u8?cookieCheck=1"
    assert rewrite_hls_location(
        "https://live.corp8.cloud/live/stream/1/index.m3u8",
        "http://live.corp8.cloud/live/stream/1/index.m3u8?cookieCheck=1",
    ) == "https://live.corp8.cloud/live/stream/1/index.m3u8?cookieCheck=1"
    segments = _playlist_refs("#EXTM3U\nsegment.ts?cookieCheck=1\n", refs[0], session="abc-uuid")
    assert segments == ["https://live.corp8.cloud/live/stream/1/segment.ts?session=abc-uuid"]
    player = _hls_player_headers("https://live.corp8.cloud/live/stream/13/index.m3u8")
    assert player["Referer"] == "https://live.corp8.cloud/camera/13"
    assert player["Origin"] == "https://live.corp8.cloud"
    assert _parse_progress_pts("out_time_us=1250000\nprogress=end\n") == 1.25
    clock: dict = {}
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first_ts, first_epoch = advance_stream_clock(clock, 100.0, base)
    second_ts, second_epoch = advance_stream_clock(clock, 105.0, base)
    reset_ts, reset_epoch = advance_stream_clock(clock, 1.0, base)
    assert first_ts == base and first_epoch == 0
    assert second_ts.timestamp() - first_ts.timestamp() == 5
    assert second_epoch == 0
    assert reset_ts == base and reset_epoch == 1
    with pytest.raises(ValueError, match="outside the configured allowlist"):
        validate_sentinel_url("https://attacker.example/stream/1")
    with pytest.raises(ValueError, match="outside the configured allowlist"):
        _playlist_refs("#EXTM3U\nhttps://attacker.example/segment.ts\n", row["hls_url"])
    poisoned = normalize_camera(
        {
            "id": "2",
            "rtsp_url": "rtsp://attacker.example:8554/stream/2",
            "hls_url": "https://attacker.example/stream/2.m3u8",
        },
        base_url="https://live.corp8.cloud",
    )
    assert poisoned["rtsp_url"] is None
    assert poisoned["hls_url"] is None
    offline = normalize_camera({"id": "9", "status": "offline", "live": False})
    assert offline["live"] is False
    assert offline["rtsp_url"] is None
    catalogue_only = normalize_camera(
        {"id": "4", "live": True, "hls_live_url": "/live/stream/4/index.m3u8"},
        base_url="https://live.corp8.cloud",
    )
    assert catalogue_only["rtsp_url"] is None
    assert catalogue_only["hls_url"] == "https://live.corp8.cloud/live/stream/4/index.m3u8"
    assert inference_url(catalogue_only) == catalogue_only["hls_url"]


def test_sentinel_resource_checklist():
    import os

    from app.workers.sentinel import (
        _is_join_decoder_warning,
        advance_stream_clock,
        grab_cmd,
        inference_url,
        normalize_camera,
    )

    assert os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS") == "rtsp_transport;tcp"
    cmd = grab_cmd("rtsp://live.corp8.cloud:8554/stream/1")
    assert cmd[cmd.index("-rtsp_transport") + 1] == "tcp"
    assert "-ss" not in cmd

    mixed = normalize_camera(
        {
            "id": "7",
            "live": True,
            "codec": "hevc",
            "width": 1920,
            "height": 1080,
            "fps": 25,
            "rtsp_url": "rtsp://live.corp8.cloud:8554/stream/7",
            "hls_live_url": "/live/stream/7/index.m3u8",
        },
        base_url="https://live.corp8.cloud",
    )
    assert mixed["codec"] == "hevc"
    assert mixed["width"] == 1920
    assert mixed["fps"] == 25
    extra = {"fps": 60, "stream_url": mixed["stream_url"]}
    clock: dict = {"fps": 60}
    base = datetime(2026, 8, 24, tzinfo=timezone.utc)
    first, epoch0 = advance_stream_clock(clock, 10.0, base)
    gapped, epoch_gap = advance_stream_clock(clock, 18.0, base)
    assert epoch0 == epoch_gap == 0
    assert (gapped - first).total_seconds() == 8
    assert extra["fps"] == 60
    cut, epoch_cut = advance_stream_clock(clock, 1.0, base)
    assert epoch_cut == 1 and cut == base
    assert _is_join_decoder_warning("Error constructing the frame RPS")
    assert _is_join_decoder_warning("[h264] Could not find ref with POC 12")
    assert not _is_join_decoder_warning("Connection timed out")
    assert inference_url({"stream_url": mixed["stream_url"], "fps": 30}) is None


def test_bytetrack_keeps_stable_ids_across_small_motion():
    from app.services.byte_track import CameraTracker

    tracker = CameraTracker()
    first = tracker.update([{"object_type": "vehicle", "confidence": 0.9, "x1": 10, "y1": 10, "x2": 50, "y2": 50}])
    second = tracker.update([{"object_type": "vehicle", "confidence": 0.9, "x1": 14, "y1": 12, "x2": 54, "y2": 52}])
    assert first[0]["local_track_id"] == second[0]["local_track_id"] == "1"
    tracker.reset()
    third = tracker.update([{"object_type": "vehicle", "confidence": 0.9, "x1": 10, "y1": 10, "x2": 50, "y2": 50}])
    assert third[0]["local_track_id"] == "1"


def test_coverage_gaps_use_camera_coordinates_not_city_labels():
    from app.services.gis import city_coverage_gap

    empty = city_coverage_gap("Bhavnagar", 21.7645, 72.1519, 4, [(23.0225, 72.5714)])
    assert empty.camera_count == 0
    assert empty.recommended_cameras == 4
    clustered = city_coverage_gap(
        "Ahmedabad",
        23.0225,
        72.5714,
        12,
        [(23.0226, 72.5715), (23.0227, 72.5716), (23.0230, 72.5720)],
    )
    assert clustered.camera_count == 3
    assert "bunched downtown" in clustered.uncovered_hint
    assert clustered.recommended_cameras == 9


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


async def test_retention_purges_old_unreferenced_events_only():
    """Old events survive if an Alert still references them; unreferenced old
    events (and their snapshot files) are purged; recent events always survive."""
    from datetime import datetime, timedelta, timezone

    from geoalchemy2.elements import WKTElement
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models.camera import Camera, Department
    from app.models.event import Alert, DetectionEvent
    from app.models.watchlist import WatchlistEntry
    from app.services.retention import purge_expired
    from app.services.storage import DATA_DIR

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=200)
    recent = now - timedelta(days=1)

    (DATA_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
    snap_path = DATA_DIR / "snapshots" / "retention-test.enc"
    snap_path.write_bytes(b"fake")
    snapshot_url = "/api/v1/evidence/snapshots/retention-test.enc"

    async with SessionLocal() as db:
        dept = Department(code="RET-TEST", name="Retention Test", zone="Test")
        db.add(dept)
        await db.flush()
        cam = Camera(
            code="RET-CAM-01",
            name="Retention Test Cam",
            department_id=dept.id,
            camera_type="ip",
            ownership="own",
            source_type="rtsp",
            location=WKTElement("POINT(72.5 23.0)", srid=4326),
            latitude=23.0,
            longitude=72.5,
            city="Test City",
        )
        db.add(cam)
        wl = WatchlistEntry(entity_type="vehicle", category="stolen_vehicle", plate_number="RT0001")
        db.add(wl)
        await db.flush()

        old_unreferenced = DetectionEvent(
            camera_id=cam.id, timestamp=old, event_type="detection", object_type="vehicle",
            snapshot_url=snapshot_url,
        )
        old_referenced = DetectionEvent(
            camera_id=cam.id, timestamp=old, event_type="detection", object_type="vehicle",
        )
        recent_event = DetectionEvent(
            camera_id=cam.id, timestamp=recent, event_type="detection", object_type="vehicle",
        )
        db.add_all([old_unreferenced, old_referenced, recent_event])
        await db.flush()

        alert = Alert(
            event_id=old_referenced.id, watchlist_id=wl.id, camera_id=cam.id,
            timestamp=old, confidence=0.9,
        )
        db.add(alert)
        await db.commit()

        old_unreferenced_id, old_referenced_id, recent_id = (
            old_unreferenced.id,
            old_referenced.id,
            recent_event.id,
        )

    try:
        result = await purge_expired(now=now)
        assert result["events_deleted"] == 1
        assert result["files_deleted"] == 1
        assert not snap_path.exists()

        async with SessionLocal() as db:
            remaining = set((await db.execute(select(DetectionEvent.id))).scalars().all())
        assert old_unreferenced_id not in remaining
        assert old_referenced_id in remaining
        assert recent_id in remaining
    finally:
        async with SessionLocal() as db:
            await db.execute(select(Alert).where(Alert.camera_id == cam.id))
            for row in list((await db.execute(select(Alert).where(Alert.camera_id == cam.id))).scalars()):
                await db.delete(row)
            for row in list((await db.execute(select(DetectionEvent).where(DetectionEvent.camera_id == cam.id))).scalars()):
                await db.delete(row)
            cam_row = await db.get(Camera, cam.id)
            if cam_row:
                await db.delete(cam_row)
            wl_row = await db.get(WatchlistEntry, wl.id)
            if wl_row:
                await db.delete(wl_row)
            dept_row = await db.get(Department, dept.id)
            if dept_row:
                await db.delete(dept_row)
            await db.commit()
        snap_path.unlink(missing_ok=True)


# --- HTTP-level integration tests -------------------------------------------
# Everything above is unit-level (imports functions/classes directly). These
# instead drive the real FastAPI `app` — routing, middleware order (CSRF, the
# request-ID/metrics observability middleware), and auth end to end — which
# nothing else in this file previously covered. httpx.AsyncClient + ASGITransport
# (not the sync TestClient) so these run on the same event loop as the async
# tests above instead of spinning up their own — mixing the two against the
# shared async engine/connection pool causes cross-event-loop asyncpg errors.

from contextlib import AsyncExitStack

from httpx import ASGITransport, AsyncClient


async def _client_with_lifespan(stack: AsyncExitStack) -> AsyncClient:
    """An AsyncClient against the real app, without running its full lifespan.

    The app's lifespan (app.main.lifespan) does one-time startup work — create
    the postgis extension/tables, seed built-in roles, warm up ArcFace in a
    background thread, and start a Redis pub/sub relay task — none of which a
    request-level test needs, since the schema/roles already exist in this
    shared dev database from the running app and earlier tests. Actually
    running it here also spawns background tasks that outlive a single test's
    AsyncExitStack (the lifespan cancels but never awaits its relay task on
    shutdown), which races with connection-pool cleanup across the tests in
    this file and intermittently raises "attached to a different loop" /
    "Event loop is closed" from asyncpg. bus.connect() is the one piece of
    lifespan state /ready's Redis check actually needs.
    """
    from app.db import engine
    from app.main import app
    from app.services.event_bus import bus

    # Each pytest-asyncio test gets its own event loop, but app.db.engine's
    # connection pool is a module-level singleton — an idle pooled connection
    # from a previous test's (now-closed) loop can otherwise get handed to
    # this test, failing on close/cancel with "Event loop is closed". Dispose
    # so this test's queries always open a fresh connection on its own loop.
    await engine.dispose()
    if bus._redis is None:
        await bus.connect()
    return await stack.enter_async_context(AsyncClient(transport=ASGITransport(app=app), base_url="http://test"))


async def test_health_is_a_pure_liveness_check():
    async with AsyncExitStack() as stack:
        client = await _client_with_lifespan(stack)
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_ready_checks_database_and_redis():
    async with AsyncExitStack() as stack:
        client = await _client_with_lifespan(stack)
        r = await client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "ok"


async def test_metrics_endpoint_exposes_prometheus_format():
    async with AsyncExitStack() as stack:
        client = await _client_with_lifespan(stack)
        await client.get("/health")  # generate at least one observed request first
        r = await client.get("/metrics")
    assert r.status_code == 200
    assert "gusip_http_requests_total" in r.text
    assert "gusip_http_request_duration_seconds" in r.text


async def test_request_id_is_generated_and_echoed():
    async with AsyncExitStack() as stack:
        client = await _client_with_lifespan(stack)
        r = await client.get("/health")
        assert r.headers.get("x-request-id")

        r2 = await client.get("/health", headers={"X-Request-ID": "test-fixed-id"})
        assert r2.headers["x-request-id"] == "test-fixed-id"


async def test_protected_endpoint_rejects_missing_auth():
    async with AsyncExitStack() as stack:
        client = await _client_with_lifespan(stack)
        r = await client.get("/api/v1/cameras")
    assert r.status_code == 401


async def test_login_then_authenticated_request_round_trip():
    async with AsyncExitStack() as stack:
        client = await _client_with_lifespan(stack)
        login = await client.post(
            "/api/v1/auth/token",
            data={"username": "operator", "password": "GUSIP@ops2026"},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]

        r = await client.get("/api/v1/cameras", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
