"""Validation and privacy-conscious logging helpers."""

from __future__ import annotations

import logging
import json
from contextvars import ContextVar
from datetime import datetime, timezone


class InputValidationError(ValueError):
    pass


class ModelServiceError(RuntimeError):
    pass


_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(value: str):
    return _request_id.set(value)


def reset_request_id(token: object) -> None:
    _request_id.reset(token)


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class _JsonFormatter(logging.Formatter):
    """Compact structured logs without request bodies, answers, or secrets."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in (
            "event", "session_id", "topic", "score", "latency_ms", "status_code",
            "input_tokens", "output_tokens", "total_tokens", "operation",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def validate_text(value: str, label: str, max_length: int) -> str:
    clean = value.strip()
    if not clean:
        raise InputValidationError(f"{label} cannot be empty.")
    if len(clean) > max_length:
        raise InputValidationError(f"{label} is too long (maximum {max_length} characters).")
    return clean


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("interview_coach")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        handler.addFilter(_RequestContextFilter())
        logger.addHandler(handler)
    return logger
