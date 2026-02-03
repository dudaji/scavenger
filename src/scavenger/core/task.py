"""Task model for Scavenger."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class Task(BaseModel):
    """Task model."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    prompt: str
    priority: int = Field(default=5, ge=1, le=10)
    working_dir: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    output_summary: Optional[str] = None

    def start(self) -> None:
        """Mark task as running."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def complete(self, summary: Optional[str] = None) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.output_summary = summary

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error

    def pause(self) -> None:
        """Mark task as paused."""
        self.status = TaskStatus.PAUSED
