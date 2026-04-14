"""MyQuant logging module.

Provides AI-friendly logging with automatic file:line tracking
and structured log format.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.logging.config import configure_logging, get_log_path
from core.logging.formatter import AIFormatter

# Logger cache to ensure same tag returns same logger
_loggers: dict[str, logging.Logger] = {}


def get_logger(tag: str) -> logging.Logger:
    """Get or create a logger with the specified tag.

    Args:
        tag: The logger tag/name (e.g., "API", "BACKTEST", "DB")

    Returns:
        A logger instance configured with AI-friendly formatting.

    Example:
        >>> logger = get_logger("API")
        >>> logger.info("request received", extra={"context": "rid=abc123"})
    """
    if tag in _loggers:
        return _loggers[tag]

    logger = logging.getLogger(tag)
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with AI formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(AIFormatter())
    logger.addHandler(console_handler)

    # File handler (if configured)
    log_path = get_log_path("api", "app")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(AIFormatter())
    logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    _loggers[tag] = logger
    return logger


__all__ = ["get_logger", "configure_logging", "get_log_path", "AIFormatter"]
