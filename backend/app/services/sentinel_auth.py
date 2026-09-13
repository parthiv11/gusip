"""Session cookie for the Sentinel Camera Grid (POST /auth/login).

Backed by Redis, not a process-local dict. The backend and worker each run
multiple replicas (k8s/apps.yaml, k8s/gpu-worker.yaml) sharing one grid
account, and the grid appears to allow only one active session per account —
replicas that each kept their own process-local cookie ended up logging in
independently and invalidating each other's session server-side. Redis gives
every replica one shared session; a small in-memory copy is kept only as a
fallback if Redis is briefly unreachable, and as a fast path to avoid a
round-trip on every call.
"""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import quote

import httpx
import redis

from app.config import get_settings
from app.services.redis_sync import get_sync_redis

log = logging.getLogger("gusip.sentinel_auth")

_lock = threading.Lock()
_cookie: str | None = None
_cookie_at = 0.0
_TTL_S = 45 * 60
# A cookie younger than this is treated as fresh even for a forced refresh —
# it was very likely just established by another concurrent caller/replica.
_MIN_REFRESH_GAP_S = 5.0
_COOKIE_KEY = "sentinel:grid:cookie"
_LOGIN_LOCK_KEY = "sentinel:grid:login_lock"
_LOGIN_LOCK_TTL_S = 20
_LOGIN_WAIT_ATTEMPTS = 30
_LOGIN_WAIT_INTERVAL_S = 0.3


def _redis_get() -> str | None:
    try:
        return get_sync_redis().get(_COOKIE_KEY)
    except redis.RedisError:
        log.debug("Sentinel session cache: Redis unavailable for read")
        return None


def _redis_set(token: str) -> None:
    try:
        get_sync_redis().set(_COOKIE_KEY, token, ex=_TTL_S)
    except redis.RedisError:
        log.debug("Sentinel session cache: Redis unavailable for write")


def _redis_clear_if(expected: str) -> None:
    try:
        client = get_sync_redis()
        if client.get(_COOKIE_KEY) == expected:
            client.delete(_COOKIE_KEY)
    except redis.RedisError:
        log.debug("Sentinel session cache: Redis unavailable for invalidate")


def grid_userinfo() -> tuple[str, str] | None:
    settings = get_settings()
    email = (settings.sentinel_email or "").strip()
    password = (settings.sentinel_password or "").strip()
    if not email or not password:
        return None
    return email, password


def grid_rtsp_url(camera_id: str) -> str | None:
    creds = grid_userinfo()
    if not creds:
        return None
    email, password = creds
    host = get_settings().sentinel_rtsp_host.strip()
    if not host or not camera_id:
        return None
    return f"rtsp://{quote(email, safe='')}:{quote(password, safe='')}@{host}:8554/stream/{camera_id}"


def grid_whep_url(camera_id: str) -> str | None:
    creds = grid_userinfo()
    if not creds:
        return None
    email, password = creds
    host = get_settings().sentinel_rtsp_host.strip()
    if not host or not camera_id:
        return None
    return f"http://{quote(email, safe='')}:{quote(password, safe='')}@{host}:8889/stream/{camera_id}/whep"


def peek_token() -> str | None:
    """Current cached token without triggering a login. For compare-and-clear invalidation."""
    with _lock:
        if _cookie:
            return _cookie
    return _redis_get()


def invalidate_session(expected: str | None = None) -> None:
    """Clear the cached session (locally and in the shared Redis cache).

    When `expected` is given, only clear if the cache still holds that exact
    token. Many camera grabs run concurrently against one shared cookie; a
    grab that started with an old token and fails minutes later must not
    discard a session another grab (in this process or another replica) has
    since (successfully) refreshed.
    """
    global _cookie, _cookie_at
    with _lock:
        if expected is None or _cookie == expected:
            _cookie = None
            _cookie_at = 0.0
    if expected is not None:
        _redis_clear_if(expected)
    else:
        try:
            get_sync_redis().delete(_COOKIE_KEY)
        except redis.RedisError:
            log.debug("Sentinel session cache: Redis unavailable for invalidate")


def _fresh_enough(force: bool, now: float) -> bool:
    if not _cookie:
        return False
    age = now - _cookie_at
    if age >= _TTL_S:
        return False
    return (not force) or age < _MIN_REFRESH_GAP_S


def _login() -> str | None:
    """POST /auth/login and return the new token, or None on failure."""
    creds = grid_userinfo()
    if not creds:
        return None
    email, password = creds
    settings = get_settings()
    origin = settings.sentinel_base_url.rstrip("/")
    headers = settings.sentinel_headers(accept="text/html, */*")
    headers["Origin"] = origin
    headers["Referer"] = f"{origin}/auth/login"
    try:
        with httpx.Client(timeout=20.0, follow_redirects=False, headers=headers) as client:
            response = client.post(f"{origin}/auth/login", data={"email": email, "password": password})
    except httpx.HTTPError as exc:
        log.warning("Sentinel login request failed")
        log.debug("Sentinel login error: %s", exc)
        return None
    token = response.cookies.get("sentinel")
    if not token:
        for cookie in response.cookies.jar:
            if cookie.name == "sentinel" and cookie.value:
                token = cookie.value
                break
    if not token:
        log.warning("Sentinel login did not return a session cookie (%s)", response.status_code)
        return None
    log.info("Sentinel grid session established")
    return token


def session_cookie(force: bool = False) -> str | None:
    """Return the shared `sentinel` cookie, logging in when needed.

    Only one replica actually performs the login: it wins a short Redis lock
    while every other caller (same process or another replica) either reads
    the session it just published, or waits briefly for it to appear. The
    grid allows only one active session per account, so letting many replicas
    log in independently causes them to invalidate each other in a loop.
    """
    global _cookie, _cookie_at
    creds = grid_userinfo()
    if not creds:
        return None

    now = time.monotonic()
    with _lock:
        if _fresh_enough(force, now):
            return _cookie

    shared = _redis_get()
    if shared and (not force):
        with _lock:
            _cookie, _cookie_at = shared, time.monotonic()
        return shared

    client = None
    try:
        client = get_sync_redis()
        got_lock = bool(client.set(_LOGIN_LOCK_KEY, "1", nx=True, ex=_LOGIN_LOCK_TTL_S))
    except redis.RedisError:
        got_lock = True  # Redis down: fall back to this process doing its own login.

    if not got_lock:
        # Another replica is logging in right now — wait for it to publish
        # the new cookie instead of also hitting /auth/login ourselves.
        for _ in range(_LOGIN_WAIT_ATTEMPTS):
            time.sleep(_LOGIN_WAIT_INTERVAL_S)
            shared = _redis_get()
            if shared:
                with _lock:
                    _cookie, _cookie_at = shared, time.monotonic()
                return shared
        log.warning("Timed out waiting for another replica's Sentinel login")

    with _lock:
        # Double-checked: the elected logger (or the one we waited for) may
        # have already refreshed while we were acquiring/waiting on the lock.
        if _fresh_enough(force, time.monotonic()):
            return _cookie
        token = _login()
        if not token:
            if client is not None and got_lock:
                try:
                    client.delete(_LOGIN_LOCK_KEY)
                except redis.RedisError:
                    pass
            return _cookie
        _cookie = token
        _cookie_at = time.monotonic()
    _redis_set(token)
    if client is not None and got_lock:
        try:
            client.delete(_LOGIN_LOCK_KEY)
        except redis.RedisError:
            pass
    return token


def apply_session(headers: dict[str, str], *, force: bool = False) -> dict[str, str]:
    token = session_cookie(force=force)
    if token:
        headers = dict(headers)
        headers["Cookie"] = f"sentinel={token}"
    return headers
