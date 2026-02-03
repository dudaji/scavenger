"""Logging utilities for Scavenger."""

import logging
import sys
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from scavenger.utils.constants import (
    DEFAULT_RETENTION_DAYS,
    LOG_DATE_FORMAT,
    LOG_FILE_BACKUP_COUNT,
    LOG_FILE_MAX_BYTES,
    LOGS_SUBDIR,
    MAIN_LOG_FILE,
    SEPARATOR_WIDTH,
    TASK_LOGS_SUBDIR,
    get_base_dir,
)


def setup_logging(
    base_dir: Optional[Path] = None,
    level: int = logging.INFO,
    console: bool = False,
) -> logging.Logger:
    """Setup logging for Scavenger.

    Args:
        base_dir: Base directory for log files
        level: Logging level
        console: Whether to also log to console

    Returns:
        Root logger for scavenger
    """
    base_dir = get_base_dir(base_dir)
    log_dir = base_dir / LOGS_SUBDIR
    log_dir.mkdir(parents=True, exist_ok=True)

    # Main log file with rotation
    main_log = log_dir / MAIN_LOG_FILE

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt=LOG_DATE_FORMAT,
    )

    # Setup root scavenger logger
    logger = logging.getLogger("scavenger")
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # File handler with rotation
    file_handler = RotatingFileHandler(
        main_log,
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (optional)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


class TaskLogger:
    """Logger for individual task executions."""

    def __init__(self, task_id: str, base_dir: Optional[Path] = None):
        self.task_id = task_id
        self.base_dir = get_base_dir(base_dir)
        self.log_dir = self.base_dir / TASK_LOGS_SUBDIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.log_dir / f"{task_id}.log"
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Setup task-specific logger."""
        self.logger = logging.getLogger(f"scavenger.task.{self.task_id}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt=LOG_DATE_FORMAT,
        )

        handler = logging.FileHandler(self.log_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def info(self, message: str) -> None:
        """Log info message."""
        self.logger.info(message)

    def error(self, message: str) -> None:
        """Log error message."""
        self.logger.error(message)

    def debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)

    def log_start(self, prompt: str, working_dir: str) -> None:
        """Log task start."""
        self.info("=" * SEPARATOR_WIDTH)
        self.info(f"Task started: {self.task_id}")
        self.info(f"Working directory: {working_dir}")
        self.info(f"Prompt: {prompt}")
        self.info("=" * SEPARATOR_WIDTH)

    def log_output(self, output: str) -> None:
        """Log task output."""
        self.info("Output:")
        for line in output.split("\n"):
            self.info(f"  {line}")

    def log_complete(self, success: bool, message: str = "") -> None:
        """Log task completion."""
        self.info("=" * SEPARATOR_WIDTH)
        if success:
            self.info("Task completed successfully")
        else:
            self.error(f"Task failed: {message}")
        self.info("=" * SEPARATOR_WIDTH)

    def get_log_content(self) -> str:
        """Read the log file content."""
        if self.log_file.exists():
            return self.log_file.read_text()
        return ""


def cleanup_old_task_logs(base_dir: Optional[Path] = None, days: int = DEFAULT_RETENTION_DAYS) -> int:
    """Remove task logs older than specified days.

    Args:
        base_dir: Base directory
        days: Number of days to keep logs

    Returns:
        Number of files removed
    """
    base_dir = get_base_dir(base_dir)
    log_dir = base_dir / TASK_LOGS_SUBDIR

    if not log_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=days)
    removed = 0

    for log_file in log_dir.glob("*.log"):
        if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
            log_file.unlink()
            removed += 1

    return removed
