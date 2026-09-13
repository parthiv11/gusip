"""Structured logging + request correlation IDs.

No observability library existed before this (grep for structlog/prometheus/
opentelemetry/sentry_sdk/correlation.?id/request.?id in backend/app returned
nothing) — debugging an incident meant grepping unstructured stdout across
however many backend/worker replicas are running, with no way to tie one
request's log lines together across them. This gives every log line a
request ID (propagated via the `X-Request-ID` response header) and, when
GUSIP_LOG_JSON is enabled, machine-parseable JSON output for a log aggregator.
"""

from __future__ import annotations

import contextvars
import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.config import get_settings

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(service: str) -> None:
    """Call once per process (API and worker each call this at startup)."""
    settings = get_settings()
    use_json = settings.log_json
    level = getattr(logging, settings.log_level.strip().upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    if use_json:
        handler.setFormatter(
            JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
                defaults={"service": service},
            )
        )
    else:
        handler.setFormatter(
            logging.Formatter(f"%(asctime)s %(levelname)s [{service}] [req=%(request_id)s] %(name)s: %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # Quiet noisy third-party loggers unless the operator raised the global level.
    for noisy in ("httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))
