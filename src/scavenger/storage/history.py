"""Execution history storage for Scavenger."""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from scavenger.core.task import Task, TaskStatus
from scavenger.utils.constants import (
    DEFAULT_STATS_DAYS,
    HISTORY_SUBDIR,
    SECONDS_PER_HOUR,
    get_base_dir,
)
from scavenger.utils.storage_helpers import safe_json_load, safe_json_save

logger = logging.getLogger("scavenger.storage")


class TaskExecution(BaseModel):
    """Record of a single task execution."""

    task_id: str
    prompt: str
    working_dir: str
    priority: int
    status: TaskStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    output_summary: Optional[str] = None

    @classmethod
    def from_task(cls, task: Task) -> "TaskExecution":
        """Create execution record from a completed task."""
        duration = None
        if task.started_at and task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()

        return cls(
            task_id=task.id,
            prompt=task.prompt,
            working_dir=task.working_dir,
            priority=task.priority,
            status=task.status,
            started_at=task.started_at,
            completed_at=task.completed_at,
            duration_seconds=duration,
            error=task.error,
            output_summary=task.output_summary,
        )


class DailyHistory(BaseModel):
    """Daily execution history."""

    date: str
    executions: list[TaskExecution] = Field(default_factory=list)
    total_completed: int = 0
    total_failed: int = 0
    total_duration_seconds: float = 0.0

    def add_execution(self, execution: TaskExecution) -> None:
        """Add an execution to the daily history."""
        self.executions.append(execution)

        if execution.status == TaskStatus.COMPLETED:
            self.total_completed += 1
        elif execution.status == TaskStatus.FAILED:
            self.total_failed += 1

        if execution.duration_seconds:
            self.total_duration_seconds += execution.duration_seconds


class HistoryStorage:
    """Storage for execution history."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = get_base_dir(base_dir)
        self.history_dir = self.base_dir / HISTORY_SUBDIR
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure history directory exists."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _get_history_file(self, target_date: date) -> Path:
        """Get history file path for a specific date."""
        return self.history_dir / f"{target_date.isoformat()}.json"

    def _load_daily_history(self, target_date: date) -> DailyHistory:
        """Load history for a specific date."""
        history_file = self._get_history_file(target_date)
        default_history = DailyHistory(date=target_date.isoformat())

        data = safe_json_load(history_file, default=default_history.model_dump())
        return DailyHistory.model_validate(data)

    def _save_daily_history(self, history: DailyHistory) -> None:
        """Save daily history to file."""
        target_date = date.fromisoformat(history.date)
        history_file = self._get_history_file(target_date)
        safe_json_save(history_file, history.model_dump(mode="json"))

    def record_execution(self, task: Task) -> None:
        """Record a task execution."""
        execution = TaskExecution.from_task(task)
        target_date = date.today()

        history = self._load_daily_history(target_date)
        history.add_execution(execution)
        self._save_daily_history(history)

    def get_history(self, target_date: Optional[date] = None) -> DailyHistory:
        """Get history for a specific date (default: today)."""
        if target_date is None:
            target_date = date.today()
        return self._load_daily_history(target_date)

    def get_recent_history(self, days: int = DEFAULT_STATS_DAYS) -> list[DailyHistory]:
        """Get history for the last N days."""
        histories = []
        today = date.today()

        for i in range(days):
            target_date = today - timedelta(days=i)
            history = self._load_daily_history(target_date)
            if history.executions:  # Only include non-empty days
                histories.append(history)

        return histories

    def list_available_dates(self) -> list[date]:
        """List all dates with history."""
        dates = []
        for file in self.history_dir.glob("*.json"):
            try:
                d = date.fromisoformat(file.stem)
                dates.append(d)
            except ValueError:
                logger.warning(f"Skipping invalid history file: {file}")
                continue
        return sorted(dates, reverse=True)

    def get_stats(self, days: int = DEFAULT_STATS_DAYS) -> dict:
        """Get aggregated stats for the last N days."""
        histories = self.get_recent_history(days)

        total_completed = sum(h.total_completed for h in histories)
        total_failed = sum(h.total_failed for h in histories)
        total_duration = sum(h.total_duration_seconds for h in histories)

        return {
            "days": len(histories),
            "total_completed": total_completed,
            "total_failed": total_failed,
            "total_executions": total_completed + total_failed,
            "total_duration_seconds": total_duration,
            "total_duration_hours": total_duration / SECONDS_PER_HOUR,
            "success_rate": total_completed / (total_completed + total_failed) * 100
            if (total_completed + total_failed) > 0
            else 0,
        }
