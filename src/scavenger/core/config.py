"""Configuration model for Scavenger."""

import logging
import os
import signal
from datetime import datetime, time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from scavenger.utils.constants import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_TIMEOUT_MINUTES,
    PID_FILE,
    get_base_dir,
)
from scavenger.utils.storage_helpers import safe_json_load, safe_json_save

logger = logging.getLogger("scavenger.config")


class ActiveHours(BaseModel):
    """Active hours configuration."""

    start: str = "01:00"
    end: str = "06:00"
    timezone: str = "Asia/Seoul"

    def is_active_now(self) -> bool:
        """Check if current time is within active hours."""
        now = datetime.now()
        current_time = now.time()

        start_time = time.fromisoformat(self.start)
        end_time = time.fromisoformat(self.end)

        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            # Overnight range (e.g., 22:00 - 06:00)
            return current_time >= start_time or current_time <= end_time


class UsageLimits(BaseModel):
    """Usage limits configuration."""

    usage_limit_by_day: dict[str, int] = Field(
        default_factory=lambda: {
            "mon": 20,
            "tue": 20,
            "wed": 20,
            "thu": 20,
            "fri": 20,
            "sat": 20,
            "sun": 20,
        }
    )
    usage_limit_default: int = 20
    usage_reset_hour: int = 6
    task_timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    session_limit_percent: int = 90

    def get_limit_for_today(self) -> int:
        """Get usage limit for current day considering reset hour."""
        now = datetime.now()

        # Determine effective day based on reset hour
        if now.hour < self.usage_reset_hour:
            # Before reset hour, use previous day's limit
            from datetime import timedelta

            effective_date = now - timedelta(days=1)
        else:
            effective_date = now

        day_name = effective_date.strftime("%a").lower()
        return self.usage_limit_by_day.get(day_name, self.usage_limit_default)


class SmtpConfig(BaseModel):
    """SMTP configuration for email notifications."""

    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password_env: str = "SCAVENGER_SMTP_PASSWORD"


class NotificationConfig(BaseModel):
    """Notification configuration."""

    email: str = ""
    smtp: SmtpConfig = Field(default_factory=SmtpConfig)
    report_time: str = "07:00"


class ClaudeCodeConfig(BaseModel):
    """Claude Code CLI configuration."""

    path: str = "claude"
    extra_args: list[str] = Field(default_factory=list)


class Config(BaseModel):
    """Main configuration model."""

    active_hours: ActiveHours = Field(default_factory=ActiveHours)
    limits: UsageLimits = Field(default_factory=UsageLimits)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    claude_code: ClaudeCodeConfig = Field(default_factory=ClaudeCodeConfig)


class ConfigStorage:
    """Configuration file storage."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = get_base_dir(base_dir)
        self.config_file = self.base_dir / DEFAULT_CONFIG_FILE
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure storage directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Config:
        """Load configuration from file."""
        default_config = Config()
        data = safe_json_load(self.config_file, default=default_config.model_dump())
        return Config.model_validate(data)

    def save(self, config: Config, notify: bool = True) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save
            notify: If True, notify running daemon to reload config immediately
        """
        safe_json_save(self.config_file, config.model_dump())
        if notify:
            self.notify_daemon()

    def notify_daemon(self) -> bool:
        """Notify running daemon to reload config via SIGUSR1.

        Returns:
            True if signal was sent successfully, False otherwise
        """
        # SIGUSR1 is Unix only
        if not hasattr(signal, "SIGUSR1"):
            return False

        pid_file = self.base_dir / PID_FILE
        if not pid_file.exists():
            return False

        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())

            # Check if process is actually running before sending signal
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
            except OSError:
                # Process doesn't exist, stale PID file
                logger.debug(f"Daemon not running (stale PID {pid})")
                return False

            os.kill(pid, signal.SIGUSR1)
            logger.info(f"Sent config reload signal to daemon (PID {pid})")
            return True
        except (ValueError, OSError, FileNotFoundError) as e:
            logger.debug(f"Could not notify daemon: {e}")
            return False

    def update(self, **kwargs) -> Config:
        """Update specific configuration values."""
        config = self.load()
        config_dict = config.model_dump()

        for key, value in kwargs.items():
            if "." in key:
                # Handle nested keys like "limits.usage_reset_hour"
                parts = key.split(".")
                target = config_dict
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
            else:
                config_dict[key] = value

        config = Config.model_validate(config_dict)
        self.save(config)
        return config
