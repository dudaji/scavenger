"""Scheduler for Scavenger."""

import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from scavenger.core.config import Config, ConfigStorage
from scavenger.core.executor import ClaudeCodeExecutor
from scavenger.core.task import Task, TaskStatus
from scavenger.storage.history import HistoryStorage
from scavenger.storage.json_storage import TaskStorage
from scavenger.utils.constants import (
    DEFAULT_CHECK_INTERVAL_SECONDS,
    ERROR_PAUSE_MULTIPLIER,
    MAX_CONSECUTIVE_ERRORS,
    MAX_TASK_WAIT_SECONDS,
    OUTPUT_SUMMARY_MAX_LENGTH,
    SECONDS_PER_MINUTE,
)
from scavenger.utils.usage_parser import get_usage_simple

logger = logging.getLogger("scavenger.scheduler")


class Scheduler:
    """Task scheduler that runs during active hours."""

    def __init__(
        self,
        task_storage: Optional[TaskStorage] = None,
        config_storage: Optional[ConfigStorage] = None,
        history_storage: Optional[HistoryStorage] = None,
        executor: Optional[ClaudeCodeExecutor] = None,
        check_interval: int = DEFAULT_CHECK_INTERVAL_SECONDS,
    ):
        self.task_storage = task_storage or TaskStorage()
        self.config_storage = config_storage or ConfigStorage()
        self.history_storage = history_storage or HistoryStorage()
        self.executor = executor or ClaudeCodeExecutor()
        self.check_interval = check_interval
        self._running = False
        self._stopping = False
        self._reload_config = False
        self._current_task: Optional[Task] = None
        self._on_task_complete: Optional[Callable[[Task], None]] = None
        self._consecutive_errors = 0
        self._max_consecutive_errors = MAX_CONSECUTIVE_ERRORS
        self._last_report_date: Optional[date] = None

    def set_on_task_complete(self, callback: Callable[[Task], None]) -> None:
        """Set callback for task completion."""
        self._on_task_complete = callback

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    def is_stopping(self) -> bool:
        """Check if scheduler is in stopping state."""
        return self._stopping

    def get_current_task(self) -> Optional[Task]:
        """Get currently running task."""
        return self._current_task

    def request_config_reload(self) -> None:
        """Request immediate config reload and check.

        Called when config changes (e.g., active hours modified).
        This will interrupt the current wait and trigger an immediate check.
        """
        logger.info("Config reload requested, will check immediately")
        self._reload_config = True

    def should_run(self, config: Config) -> tuple[bool, str]:
        """Check if scheduler should run tasks now.

        Returns:
            Tuple of (should_run, reason)
        """
        # Check if stopping
        if self._stopping:
            return False, "Scheduler is stopping"

        # Check active hours
        if not config.active_hours.is_active_now():
            return False, "Outside active hours"

        # Check usage limit
        usage = get_usage_simple(config.claude_code.path)
        # If usage fetch failed (returns -1 or None), skip task execution
        if not usage or not usage.is_valid():
            return False, "Unable to fetch usage info, skipping task"

        limit = config.limits.get_limit_for_today()
        if not usage.is_within_limit(limit):
            return False, f"Usage limit reached ({usage.weekly_percent:.1f}% >= {limit}%)"

        # Check if there are pending tasks
        next_task = self.task_storage.get_next_pending()
        if not next_task:
            return False, "No pending tasks"

        return True, "Ready to run"

    def _recover_interrupted_tasks(self) -> None:
        """Recover tasks that were interrupted (stuck in running state)."""
        tasks = self.task_storage.list_all()
        for task in tasks:
            if task.status == TaskStatus.RUNNING:
                logger.warning(f"Found interrupted task {task.id}, marking as failed")
                task.fail("Task interrupted (daemon restart)")
                self.task_storage.update(task)
                self.history_storage.record_execution(task)

    def run_next_task(self, config: Config) -> Optional[Task]:
        """Run the next pending task."""
        task = self.task_storage.get_next_pending()
        if not task:
            return None

        self._current_task = task
        logger.info(f"Starting task {task.id}: {task.prompt[:50]}...")

        task.start()
        self.task_storage.update(task)

        try:
            result = self.executor.execute(
                prompt=task.prompt,
                working_dir=task.working_dir,
                timeout_minutes=config.limits.task_timeout_minutes,
                task_id=task.id,
            )

            if result.success:
                summary = result.output[:OUTPUT_SUMMARY_MAX_LENGTH] if result.output else "Completed"
                task.complete(summary)
                logger.info(f"Task {task.id} completed successfully")
                self._consecutive_errors = 0
            else:
                task.fail(result.error or "Unknown error")
                logger.error(f"Task {task.id} failed: {result.error}")
                self._consecutive_errors += 1

        except Exception as e:
            task.fail(str(e))
            logger.exception(f"Task {task.id} failed with exception")
            self._consecutive_errors += 1

        finally:
            self._current_task = None
            self.task_storage.update(task)
            self.history_storage.record_execution(task)

            if self._on_task_complete:
                try:
                    self._on_task_complete(task)
                except Exception:
                    logger.exception("Error in task completion callback")

        return task

    def run_loop(self) -> None:
        """Main scheduler loop."""
        self._running = True
        self._stopping = False
        self._consecutive_errors = 0

        logger.info("Scheduler started")

        # Recover any interrupted tasks from previous run
        self._recover_interrupted_tasks()

        while self._running:
            try:
                # Check for too many consecutive errors
                if self._consecutive_errors >= self._max_consecutive_errors:
                    logger.error(
                        f"Too many consecutive errors ({self._consecutive_errors}), "
                        f"pausing for extended period"
                    )
                    time.sleep(self.check_interval * ERROR_PAUSE_MULTIPLIER)
                    self._consecutive_errors = 0

                config = self.config_storage.load()

                # Check if it's time to send daily report
                self._check_and_send_report(config)

                should_run, reason = self.should_run(config)

                if should_run:
                    self.run_next_task(config)
                else:
                    logger.info(f"Skipping: {reason}")

                # Wait before next check (interruptible)
                self._wait_interruptible(self.check_interval)

            except Exception:
                logger.exception("Error in scheduler loop")
                self._consecutive_errors += 1
                self._wait_interruptible(self.check_interval)

        logger.info("Scheduler stopped")

    def _check_and_send_report(self, config: Config) -> None:
        """Check if it's time to send the daily report and send it."""
        if not config.notification.email:
            return

        now = datetime.now()
        report_time_str = config.notification.report_time

        try:
            report_hour, report_minute = map(int, report_time_str.split(":"))
        except ValueError:
            logger.warning(f"Invalid report time format: {report_time_str}")
            return

        # Check if current time matches report time (within check_interval window)
        if now.hour == report_hour and now.minute < report_minute + (self.check_interval // SECONDS_PER_MINUTE + 1):
            # Check if we already sent report today
            today = date.today()
            if self._last_report_date == today:
                return

            # Only send if we're within the first few minutes of report time
            if now.minute >= report_minute and now.minute < report_minute + 5:
                logger.info("Sending daily report...")
                self._send_daily_report(today - timedelta(days=1))  # Report for yesterday
                self._last_report_date = today

    def _send_daily_report(self, report_date: date) -> None:
        """Send the daily report email."""
        try:
            from scavenger.notification.email import EmailSender

            sender = EmailSender()
            if sender.is_configured():
                result = sender.send_daily_report(report_date)
                if result.success:
                    logger.info(f"Daily report sent: {result.message}")
                else:
                    logger.error(f"Failed to send daily report: {result.message}")
            else:
                logger.warning("Email not configured, skipping daily report")
        except Exception:
            logger.exception("Error sending daily report")

    def _wait_interruptible(self, seconds: int) -> None:
        """Wait for specified seconds, but can be interrupted by stop() or config reload."""
        for _ in range(seconds):
            if not self._running:
                break
            if self._reload_config:
                self._reload_config = False
                logger.info("Wait interrupted for config reload")
                break
            time.sleep(1)

    def stop(self, graceful: bool = True) -> None:
        """Stop the scheduler.

        Args:
            graceful: If True, wait for current task to complete
        """
        if graceful and self._current_task:
            logger.info("Stopping scheduler gracefully, waiting for current task...")
            self._stopping = True
            # Wait for current task to complete (with timeout)
            for _ in range(MAX_TASK_WAIT_SECONDS):
                if self._current_task is None:
                    break
                time.sleep(1)

        logger.info("Stopping scheduler...")
        self._running = False

    def force_stop(self) -> None:
        """Force stop the scheduler immediately."""
        logger.warning("Force stopping scheduler")
        self._running = False
        self._stopping = False

        # Mark current task as failed if any
        if self._current_task:
            self._current_task.fail("Forced shutdown")
            self.task_storage.update(self._current_task)
            self.history_storage.record_execution(self._current_task)
            self._current_task = None
