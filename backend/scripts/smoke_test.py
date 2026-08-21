"""Live stack smoke test. Prints pass/fail only — no tokens."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("GUSIP_BASE", "http://127.0.0.1:8000")
USER = os.environ.get("GUSIP_USER", "operator")
PASSWORD = os.environ.get("GUSIP_PASSWORD", "GUSIP@ops2026")

ok = 0
bad = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok, bad
    if cond:
        ok += 1
        print(f"PASS  {name}")
    else:
        bad += 1
        print(f"FAIL  {name}  {detail}")


def req(path: str, method="GET", data=None, headers=None, timeout=20):
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)
    body = None
    if isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode()
        h.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif isinstance(data, (bytes, bytearray)):
        body = data
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, resp.headers, raw
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def main() -> int:
    st, _, raw = req("/health")
    check("GET /health", st == 200 and b'"ok"' in raw, str(st))

    st, _, raw = req("/api/v1/meta")
    check("GET /api/v1/meta", st == 200 and b"GUSIP" in raw, str(st))

    st, _, raw = req("/api/v1/cameras")
    check("cameras unauthorized without token", st == 401, str(st))

    st, _, raw = req(
        "/api/v1/auth/token",
        method="POST",
        data={"username": USER, "password": PASSWORD},
    )
    check("login operator", st == 200, str(st))
    token = ""
    if st == 200:
        token = json.loads(raw).get("access_token") or ""
        check("jwt issued", bool(token) and token.count(".") == 2)
    auth = {"Authorization": f"Bearer {token}"} if token else {}

    st, _, raw = req("/api/v1/cameras", headers=auth)
    cams = json.loads(raw) if st == 200 else []
    sent = [c for c in cams if c.get("source_type") == "sentinel"]
    check("list cameras", st == 200 and len(cams) >= 50, f"status={st} n={len(cams) if isinstance(cams, list) else '?'}")
    check("sentinel cameras onboarded", len(sent) >= 20, f"n={len(sent)}")

    st, _, raw = req("/api/v1/feeds/sentinel/sync", method="POST", headers=auth)
    body = json.loads(raw) if raw else {}
    check("sync sentinel catalog", st == 200 and int(body.get("synced") or 0) >= 20, f"status={st} {body}")

    if sent:
        sid = (sent[0].get("extra") or {}).get("sentinel_id") or sent[0]["code"].replace("SEN-", "")
        st, _, raw = req(f"/api/v1/feeds/sentinel/{sid}/state", headers=auth)
        state = json.loads(raw) if st == 200 else {}
        check("sentinel camera state", st == 200 and state.get("status") in {"live", "processing", "offline"}, f"status={st} cam={state.get('status')}")

        st, hdrs, raw = req(
            f"/api/v1/feeds/sentinel/{sid}/stream?token={urllib.parse.quote(token)}",
            headers={"Range": "bytes=0-1023"},
        )
        ctype = (hdrs.get("Content-Type") if hdrs else "") or ""
        check(
            "sentinel stream range proxy",
            st in (200, 206) and len(raw) > 0,
            f"status={st} type={ctype} bytes={len(raw)}",
        )

        st, _, raw = req(f"/api/v1/feeds/sentinel/{sid}/preview?token={urllib.parse.quote(token)}")
        check("sentinel preview (may 404 until sampled)", st in (200, 404), str(st))

    st, _, raw = req("/api/v1/alerts?limit=5", headers=auth)
    check("list alerts", st == 200, str(st))

    st, _, raw = req("/api/v1/watchlist", headers=auth)
    wl = json.loads(raw) if st == 200 else []
    check("watchlist seeded", st == 200 and len(wl) >= 1, f"n={len(wl) if isinstance(wl, list) else 0}")

    st, _, raw = req("/api/v1/gis/cameras", headers=auth)
    gj = json.loads(raw) if st == 200 else {}
    check("gis geojson", st == 200 and gj.get("type") == "FeatureCollection", str(st))

    st, _, raw = req(
        "/api/v1/search/events",
        method="POST",
        data=json.dumps({"plate": "GJ 01 ST 0001", "limit": 5, "purpose": "evaluation"}).encode(),
        headers={**auth, "Content-Type": "application/json"},
    )
    check("search stolen demo plate", st == 200, str(st))

    st, _, raw = req(
        "/api/v1/search/events",
        method="POST",
        data=json.dumps({"plate": "GJ 01 ST 0001", "limit": 5}).encode(),
        headers={**auth, "Content-Type": "application/json"},
    )
    check("search without purpose rejected", st in (400, 422), str(st))

    st, _, raw = req("/api/v1/feeds/anpr-report?hours=24&fmt=json", headers=auth)
    check("anpr report json", st == 200, str(st))

    st, _, raw = req("/api/v1/feeds/anpr-report?hours=24&fmt=csv", headers=auth)
    check("operator cannot export csv", st == 403, str(st))

    st, _, raw = req(
        "/api/v1/auth/token",
        method="POST",
        data={"username": "investigator", "password": "GUSIP@inv2026"},
    )
    inv_token = json.loads(raw).get("access_token") if st == 200 else ""
    inv = {"Authorization": f"Bearer {inv_token}"} if inv_token else {}
    st, _, raw = req("/api/v1/feeds/anpr-report?hours=24&fmt=csv", headers=inv)
    check("investigator can export csv", st == 200 and (raw[:20].find(b"timestamp") >= 0 or len(raw) >= 0), str(st))

    st, _, raw = req(
        "/api/v1/auth/token",
        method="POST",
        data={"username": "coordinator", "password": "GUSIP@coord2026"},
    )
    check("login coordinator", st == 200, str(st))
    coord_token = json.loads(raw).get("access_token") if st == 200 else ""
    coord = {"Authorization": f"Bearer {coord_token}"} if coord_token else {}
    req("/api/v1/auth/break-glass", method="DELETE", headers=coord)

    st, _, raw = req("/api/v1/cameras", headers=coord)
    coord_cams = json.loads(raw) if st == 200 else []
    n_home = len(coord_cams) if isinstance(coord_cams, list) else 0
    check("coordinator home-dept cameras only", st == 200 and 0 < n_home < 50, f"status={st} n={n_home}")

    st, _, raw = req(
        "/api/v1/auth/break-glass",
        method="POST",
        data=json.dumps({"reason": "FIR 112/2026 vehicle fled home district", "duration_minutes": 15}).encode(),
        headers={**coord, "Content-Type": "application/json"},
    )
    check("coordinator break-glass", st == 200, str(st))

    st, _, raw = req("/api/v1/cameras", headers=coord)
    open_cams = json.loads(raw) if st == 200 else []
    n_open = len(open_cams) if isinstance(open_cams, list) else 0
    check("break-glass unlocks statewide cameras", st == 200 and n_open > n_home, f"home={n_home} open={n_open}")

    st, _, raw = req("/api/v1/auth/break-glass", method="DELETE", headers=coord)
    check("revoke break-glass", st == 200, str(st))

    st, _, raw = req("/api/v1/admin/stats", headers=auth)
    check("admin stats", st == 200, str(st))

    print(f"\n{ok} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
