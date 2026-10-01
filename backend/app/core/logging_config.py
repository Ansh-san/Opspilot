"""
OpsPilot — Structured Logging Configuration

Uses Python's standard logging module configured for structured output.
In production, logs are emitted as JSON. In development, human-readable.
"""

import logging
import sys

from app.core.config import settings
from app.core.middleware import request_id_var


def setup_logging() -> None:
    """Configure application logging."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    if settings.is_production:
        # JSON formatter for log aggregation in production (CloudWatch / Datadog)
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | [%(request_id)s] | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # We need to inject request_id into the LogRecord and redact PII globally
    from app.core.redactor import redact_string, redact_data
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = request_id_var.get()
        if isinstance(record.msg, str):
            record.msg = redact_string(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(redact_data(list(record.args)))
            elif isinstance(record.args, dict):
                record.args = redact_data(record.args)
        return record
    logging.setLogRecordFactory(record_factory)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log: dict = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            log["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log.update(record.extra)  # type: ignore[arg-type]
        if hasattr(record, "org_id"):
            log["org_id"] = str(record.org_id)
        if hasattr(record, "user_id"):
            log["user_id"] = str(record.user_id)
        return json.dumps(log)
