"""Prometheus metrics for the API (`GET /metrics`).

No metrics endpoint existed before this — grep for prometheus/opentelemetry in
backend/app returned nothing, so there was no way to see request rate, error
rate, or latency without shipping logs somewhere first.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUESTS_TOTAL = Counter(
    "gusip_http_requests_total",
    "Total HTTP requests handled by the API",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "gusip_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
