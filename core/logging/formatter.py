"""AI-friendly log formatter.

Format: [TS] [TAG] [LEVEL] msg | context | file:line
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path


class AIFormatter(logging.Formatter):
    """AI-friendly log formatter.

    Produces structured logs in the format:
        [2026-04-11 15:30:00] [TAG] [LEVEL] msg | context | file:line

    This format is designed to be:
    - Machine parseable (LLM friendly)
    - Human readable
    - Traceable (includes file:line)
    """

    def __init__(self) -> None:
        """Initialize the AI formatter."""
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record into an AI-friendly string.

        Args:
            record: The log record to format.

        Returns:
            Formatted log string.
        """
        # Timestamp in local time
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

        # Tag (logger name)
        tag = record.name.upper()

        # Level name
        level = record.levelname

        # Message
        msg = record.getMessage()

        # Build log parts
        parts = [
            f"[{timestamp}]",
            f"[{tag}]",
            f"[{level}]",
            msg,
        ]

        # Add context if available (from extra param)
        context = getattr(record, "context", None)
        if context:
            if isinstance(context, dict):
                context_str = " | ".join(f"{k}={v}" for k, v in context.items())
                parts.append(context_str)
            else:
                parts.append(str(context))

        # Add source location (file:line)
        if record.pathname and record.lineno:
            # Get just the filename, not full path
            filename = Path(record.pathname).name
            parts.append(f"{filename}:{record.lineno}")

        return " | ".join(parts)


__all__ = ["AIFormatter"]
