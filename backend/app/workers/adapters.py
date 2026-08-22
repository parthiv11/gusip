"""Departmental VMS adapters (RTSP / ONVIF / vendor API). Existing VMS stay independent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class Adapter(Protocol):
    source_type: str

    async def health(self, camera: dict[str, Any]) -> str: ...

    async def pull_metadata(self, camera: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class RtspAdapter:
    source_type: str = "rtsp"

    async def health(self, camera: dict[str, Any]) -> str:
        # PoC: treat configured RTSP cameras as reachable unless marked offline.
        return "online" if camera.get("rtsp_url") else "degraded"

    async def pull_metadata(self, camera: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocol": "RTSP",
            "url": camera.get("rtsp_url"),
            "transport": "tcp",
            "note": "Frames stay on departmental NVR; adapter samples for AI only.",
        }


@dataclass
class OnvifAdapter:
    source_type: str = "onvif"

    async def health(self, camera: dict[str, Any]) -> str:
        return "online" if camera.get("onvif_endpoint") else "degraded"

    async def pull_metadata(self, camera: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocol": "ONVIF Profile S/T",
            "endpoint": camera.get("onvif_endpoint"),
            "services": ["Media", "PTZ", "Events"],
            "note": "Read-only pull. No write to source VMS.",
        }


@dataclass
class VendorApiAdapter:
    source_type: str = "vendor_api"

    async def health(self, camera: dict[str, Any]) -> str:
        return "online" if camera.get("vendor_api_ref") else "degraded"

    async def pull_metadata(self, camera: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocol": "vendor_sdk",
            "ref": camera.get("vendor_api_ref"),
            "vendor": camera.get("vendor"),
            "note": "Hikvision/Dahua/UNV-style replay API. Department VMS remains source of truth.",
        }


@dataclass
class SentinelAdapter:
    source_type: str = "sentinel"

    async def health(self, camera: dict[str, Any]) -> str:
        return "online" if camera.get("vendor_api_ref") else "degraded"

    async def pull_metadata(self, camera: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocol": "sentinel_ingest",
            "portal": "https://live.sentinelgujarat.in",
            "catalogue": "/api/ingest",
            "rtsp": "rtsp://<host>:8554/stream/<id> over TCP",
            "hls": "/live/stream/<id>/index.m3u8",
            "whep": ":8889/stream/<id>/whep",
            "note": "Official grid. Inference = RTSP TCP. Wall = HLS, HTTP /stream is browser fallback only.",
        }


ADAPTERS: dict[str, Adapter] = {
    "rtsp": RtspAdapter(),
    "onvif": OnvifAdapter(),
    "vendor_api": VendorApiAdapter(),
    "sentinel": SentinelAdapter(),
}


def get_adapter(source_type: str) -> Adapter:
    return ADAPTERS.get(source_type, RtspAdapter())
