"""JSON file storage for Scavenger."""

import logging
from pathlib import Path
from typing import Optional

from scavenger.core.task import Task, TaskStatus
from scavenger.utils.constants import DEFAULT_TASKS_FILE, get_base_dir
from scavenger.utils.storage_helpers import safe_json_load, safe_json_save

logger = logging.getLogger("scavenger.storage")


class TaskStorage:
    """JSON-based task storage."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = get_base_dir(base_dir)
        self.tasks_file = self.base_dir / DEFAULT_TASKS_FILE
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure storage directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _load_tasks(self) -> list[Task]:
        """Load tasks from JSON file."""
        data = safe_json_load(self.tasks_file, default=[])
        return [Task.model_validate(t) for t in data]

    def _save_tasks(self, tasks: list[Task]) -> None:
        """Save tasks to JSON file."""
        data = [t.model_dump(mode="json") for t in tasks]
        safe_json_save(self.tasks_file, data)

    def add(self, task: Task) -> Task:
        """Add a new task."""
        tasks = self._load_tasks()
        tasks.append(task)
        self._save_tasks(tasks)
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        tasks = self._load_tasks()
        for task in tasks:
            if task.id == task_id:
                return task
        return None

    def list_all(self) -> list[Task]:
        """List all tasks."""
        return self._load_tasks()

    def list_pending(self) -> list[Task]:
        """List pending tasks sorted by priority."""
        tasks = self._load_tasks()
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]
        return sorted(pending, key=lambda t: t.priority)

    def update(self, task: Task) -> None:
        """Update an existing task."""
        tasks = self._load_tasks()
        for i, t in enumerate(tasks):
            if t.id == task.id:
                tasks[i] = task
                break
        self._save_tasks(tasks)

    def remove(self, task_id: str) -> bool:
        """Remove a task by ID."""
        tasks = self._load_tasks()
        original_len = len(tasks)
        tasks = [t for t in tasks if t.id != task_id]
        if len(tasks) < original_len:
            self._save_tasks(tasks)
            return True
        return False

    def get_next_pending(self) -> Optional[Task]:
        """Get the next pending task with highest priority (lowest number)."""
        pending = self.list_pending()
        return pending[0] if pending else None
