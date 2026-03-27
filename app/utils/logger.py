"""Structured logging utilities."""

import logging
import json
from datetime import datetime
from typing import Any, Optional


class StructuredLogger:
    """Structured logging helper."""

    def __init__(self, name: str):
        """Initialize logger."""
        self.logger = logging.getLogger(name)

    def _log(self, level: int, msg: str, **kwargs):
        """Log with structured context."""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": msg,
            **kwargs,
        }
        self.logger.log(level, json.dumps(context, default=str))

    def info(self, msg: str, **kwargs):
        """Log info level."""
        self._log(logging.INFO, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        """Log error level."""
        self._log(logging.ERROR, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning level."""
        self._log(logging.WARNING, msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        """Log debug level."""
        self._log(logging.DEBUG, msg, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger."""
    return StructuredLogger(name)
