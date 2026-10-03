"""Structured JSON logging with a whitelisted, secret-free field set.

Every module that needs to log an operational event should call
:func:`log_event` instead of the stdlib logger directly. The function only
accepts a fixed set of fields (timestamp, level, module, operation, source,
game_id, model_version, feature_version) and refuses any keyword whose name
looks like it could carry a credential. This keeps HANDOFF rule "no secrets in
Settings, logs or the repository" enforced in code, not only by convention.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Any

#: The only structured fields a log record may carry beyond level/message.
ALLOWED_FIELDS: tuple[str, ...] = (
    "operation",
    "source",
    "game_id",
    "model_version",
    "feature_version",
)

#: Substrings that mark a field name as unsafe to log, regardless of intent.
_FORBIDDEN_NAME_SUBSTRINGS: tuple[str, ...] = (
    "key",
    "token",
    "secret",
    "password",
    "credential",
    "authorization",
    "cookie",
)


class SensitiveFieldError(ValueError):
    """Raised when a caller tries to attach a credential-shaped field to a log."""


def _reject_sensitive_names(field_names: tuple[str, ...]) -> None:
    """Guard used by :func:`log_event`. Exercised directly in tests because the
    current keyword-only signature already only offers safe names; this keeps
    the guard correct if the signature is ever loosened to ``**kwargs``."""

    for name in field_names:
        lowered = name.lower()
        if any(bad in lowered for bad in _FORBIDDEN_NAME_SUBSTRINGS):
            raise SensitiveFieldError(f"refusing to log field that looks sensitive: {name}")


class JsonFormatter(logging.Formatter):
    """Render one JSON object per record with a fixed, predictable shape."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        for field in ALLOWED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, sort_keys=True, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Point the root logger at a single JSON stream handler, idempotently."""

    root = logging.getLogger()
    root.setLevel(level)
    if any(isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    """Return a plain stdlib logger; formatting is applied at the root handler."""

    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.INFO,
    operation: str | None = None,
    source: str | None = None,
    game_id: str | None = None,
    model_version: str | None = None,
    feature_version: str | None = None,
) -> None:
    """Log one structured event using only the whitelisted keyword fields.

    The keyword-only signature is the primary guarantee: a caller cannot pass
    an arbitrary field name, so a credential cannot end up in a log line under
    some ad-hoc key. :func:`_reject_sensitive_names` is a second guard for the
    day this signature is loosened to ``**kwargs``.
    """

    fields = {
        "operation": operation,
        "source": source,
        "game_id": game_id,
        "model_version": model_version,
        "feature_version": feature_version,
    }
    _reject_sensitive_names(tuple(fields))
    extra = {name: value for name, value in fields.items() if value is not None}
    logger.log(level, message, extra=extra)
