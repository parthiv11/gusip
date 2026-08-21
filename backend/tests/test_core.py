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
