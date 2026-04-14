"""Logging configuration utilities."""
from __future__ import annotations

import logging
from pathlib import Path


def get_log_path(module: str, log_type: str) -> Path:
    """Get the log file path for a given module and type.

    Args:
        module: The module name (e.g., "api", "web", "start")
        log_type: The log type (e.g., "app", "access", "error")

    Returns:
        Path to the log file.

    Example:
        >>> get_log_path("api", "app")
        PosixPath('/path/to/project/logs/api/api_20260411.log')
    """
    # Get project root (assuming we're in core/logging/)
    project_root = Path(__file__).parent.parent.parent
    log_root = project_root / "logs"

    # Get current date for log filename
    from datetime import datetime
    log_date = datetime.now().strftime("%Y%m%d")

    # Build log file path
    log_dir = log_root / module
    log_file = log_dir / f"{log_type}_{log_date}.log"

    return log_file


def configure_logging(
    level: int | str = logging.INFO,
    log_to_file: bool = True,
) -> None:
    """Configure the root logging system.

    Args:
        level: The logging level (default: INFO).
        log_to_file: Whether to log to files (default: True).
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
    ))
    root_logger.addHandler(console_handler)


__all__ = ["get_log_path", "configure_logging"]
