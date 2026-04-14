"""Tests for core.logging module."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest


class TestGetLogger:
    """Test get_logger factory function."""

    def test_returns_logger_with_tag(self, tmp_path):
        """Should return a logger with the specified tag."""
        from core.logging import get_logger

        logger = get_logger("TEST")
        assert logger.name == "TEST"

    def test_different_tags_return_different_loggers(self):
        """Different tags should return different logger instances."""
        from core.logging import get_logger

        logger1 = get_logger("API")
        logger2 = get_logger("BACKTEST")
        assert logger1 is not logger2

    def test_same_tag_returns_same_logger(self):
        """Same tag should return the same logger instance."""
        from core.logging import get_logger

        logger1 = get_logger("API")
        logger2 = get_logger("API")
        assert logger1 is logger2


class TestLogFormatter:
    """Test AI-friendly log formatter."""

    def test_format_includes_timestamp_tag_level(self, tmp_path):
        """Log format should include [TS] [TAG] [LEVEL]."""
        from core.logging import get_logger
        from core.logging.formatter import AIFormatter

        formatter = AIFormatter()
        record = logging.LogRecord(
            name="TEST", level=logging.INFO, pathname="test.py", lineno=42,
            msg="test message", args=(), exc_info=None
        )
        formatted = formatter.format(record)

        # 检查格式
        assert re.match(r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]', formatted)  # [TS]
        assert '[TEST]' in formatted  # [TAG]
        assert '[INFO]' in formatted  # [LEVEL]

    def test_format_includes_source_location(self, tmp_path):
        """Log format should include file:line."""
        from core.logging import get_logger
        from core.logging.formatter import AIFormatter

        formatter = AIFormatter()
        record = logging.LogRecord(
            name="API", level=logging.INFO, pathname="api/routes.py", lineno=23,
            msg="request received", args=(), exc_info=None
        )
        formatted = formatter.format(record)

        # Formatter只保留文件名，不包含路径
        assert 'routes.py:23' in formatted

    def test_format_with_context(self, tmp_path):
        """Log format should include context when provided."""
        from core.logging.formatter import AIFormatter
        import logging

        formatter = AIFormatter()
        record = logging.LogRecord(
            name="BACKTEST", level=logging.INFO, pathname="test.py", lineno=1,
            msg="backtest completed", args=(), exc_info=None
        )
        # 添加上下文
        record.context = {"return": "15.2%", "sharpe": "1.85"}
        formatted = formatter.format(record)

        assert "return=15.2%" in formatted
        assert "sharpe=1.85" in formatted


class TestLogConfig:
    """Test logging configuration."""

    def test_log_files_created_in_correct_directory(self, tmp_path):
        """Log files should be created in logs/ directory."""
        # 测试日志文件路径配置
        from core.logging.config import get_log_path

        log_path = str(get_log_path("api", "app"))
        assert "logs" in log_path
        assert "api" in log_path
        assert "app" in log_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
