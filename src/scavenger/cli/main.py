"""Main CLI entry point for Scavenger."""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from scavenger import __version__
from scavenger.cli import config_commands, daemon_commands, history_commands, report_commands
from scavenger.core.executor import ClaudeCodeExecutor
from scavenger.core.task import Task, TaskStatus
from scavenger.storage.json_storage import TaskStorage
from scavenger.utils.cli_helpers import (
    get_status_color,
    truncate_directory,
    truncate_prompt,
)
from scavenger.utils.constants import (
    DEFAULT_TIMEOUT_MINUTES,
    OUTPUT_SUMMARY_MAX_LENGTH,
    PROMPT_DISPLAY_MAX,
    SECONDS_PER_MINUTE,
)
from scavenger.utils.usage_parser import get_usage_simple

app = typer.Typer(
    name="scavenger",
    help="Automated task runner for Claude Code during inactive hours.",
    no_args_is_help=True,
)
console = Console()

# Add subcommands
app.add_typer(config_commands.app, name="config")
app.add_typer(daemon_commands.app, name="daemon")
app.add_typer(history_commands.app, name="history")
app.add_typer(report_commands.app, name="report")

# Top-level start/stop commands (shortcuts for daemon start/stop)
app.command("start")(daemon_commands.start_daemon)
app.command("stop")(daemon_commands.stop_daemon)


def get_storage() -> TaskStorage:
    """Get task storage instance."""
    return TaskStorage()


def get_executor() -> ClaudeCodeExecutor:
    """Get Claude Code executor instance."""
    return ClaudeCodeExecutor()


@app.command()
def add(
    prompt: str = typer.Argument(..., help="Task prompt for Claude Code"),
    priority: int = typer.Option(5, "--priority", "-p", help="Priority (1=highest, 10=lowest)", min=1, max=10),
    working_dir: Optional[str] = typer.Option(None, "--dir", "-d", help="Working directory for the task"),
) -> None:
    """Add a new task to the queue."""
    if working_dir is None:
        working_dir = os.getcwd()

    working_dir = str(Path(working_dir).resolve())

    if not Path(working_dir).exists():
        console.print(f"[red]Error:[/red] Directory does not exist: {working_dir}")
        raise typer.Exit(1)

    storage = get_storage()
    task = Task(prompt=prompt, priority=priority, working_dir=working_dir)
    storage.add(task)

    console.print(f"[green]Task added:[/green] {task.id}")
    console.print(f"  Priority: {task.priority}")
    console.print(f"  Directory: {task.working_dir}")
    console.print(f"  Prompt: {task.prompt[:50]}..." if len(task.prompt) > 50 else f"  Prompt: {task.prompt}")


@app.command("list")
def list_tasks(
    all_tasks: bool = typer.Option(False, "--all", "-a", help="Show all tasks including completed"),
) -> None:
    """List tasks in the queue."""
    storage = get_storage()
    tasks = storage.list_all()

    if not all_tasks:
        tasks = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED)]

    if not tasks:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(title="Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Priority", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Prompt", max_width=PROMPT_DISPLAY_MAX)
    table.add_column("Directory", max_width=30)

    for task in sorted(tasks, key=lambda t: (t.status != TaskStatus.RUNNING, t.priority)):
        status_color = get_status_color(task.status)
        prompt_display = truncate_prompt(task.prompt)
        dir_display = truncate_directory(task.working_dir)

        table.add_row(
            task.id,
            str(task.priority),
            f"[{status_color}]{task.status.value}[/{status_color}]",
            prompt_display,
            dir_display,
        )

    console.print(table)


@app.command()
def remove(
    task_id: str = typer.Argument(..., help="Task ID to remove"),
) -> None:
    """Remove a task from the queue."""
    storage = get_storage()

    if storage.remove(task_id):
        console.print(f"[green]Task removed:[/green] {task_id}")
    else:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        raise typer.Exit(1)


@app.command()
def run(
    task_id: Optional[str] = typer.Argument(None, help="Specific task ID to run (default: next pending)"),
    timeout: int = typer.Option(DEFAULT_TIMEOUT_MINUTES, "--timeout", "-t", help="Timeout in minutes"),
) -> None:
    """Run a task manually."""
    from scavenger.storage.history import HistoryStorage

    storage = get_storage()
    history_storage = HistoryStorage()
    executor = get_executor()

    if task_id:
        task = storage.claim_by_id(task_id)
        if not task:
            console.print(f"[red]Error:[/red] Task not found or not pending: {task_id}")
            raise typer.Exit(1)
    else:
        task = storage.claim_next_pending()
        if not task:
            console.print("[dim]No pending tasks to run.[/dim]")
            return

    console.print(f"[blue]Running task:[/blue] {task.id}")
    console.print(f"  Prompt: {task.prompt[:80]}..." if len(task.prompt) > 80 else f"  Prompt: {task.prompt}")
    console.print(f"  Directory: {task.working_dir}")
    console.print()

    try:
        with console.status("[bold blue]Executing with Claude Code...[/bold blue]"):
            result = executor.execute(
                prompt=task.prompt,
                working_dir=task.working_dir,
                timeout_minutes=timeout,
                task_id=task.id,
            )

        if result.success:
            summary = result.output[:OUTPUT_SUMMARY_MAX_LENGTH] if result.output else "Completed"
            task.complete(summary)
            console.print("[green]Task completed successfully![/green]")
            if result.output:
                console.print("\n[bold]Output:[/bold]")
                console.print(result.output)
        else:
            task.fail(result.error or "Unknown error")
            console.print(f"[red]Task failed:[/red] {result.error}")

    except Exception as e:
        task.fail(str(e))
        console.print(f"[red]Task failed with exception:[/red] {e}")

    finally:
        storage.update(task)
        history_storage.record_execution(task)


@app.command()
def status() -> None:
    """Show scavenger status."""
    from scavenger.core.config import ConfigStorage
    from scavenger.core.daemon import Daemon
    from scavenger.storage.history import HistoryStorage

    storage = get_storage()
    config_storage = ConfigStorage()
    history_storage = HistoryStorage()
    daemon = Daemon()

    tasks = storage.list_all()
    config = config_storage.load()

    pending = len([t for t in tasks if t.status == TaskStatus.PENDING])
    running = len([t for t in tasks if t.status == TaskStatus.RUNNING])
    completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    failed = len([t for t in tasks if t.status == TaskStatus.FAILED])

    # Daemon status
    console.print("[bold]Daemon[/bold]")
    if daemon.is_running():
        console.print(f"  Status: [green]Running[/green] (PID: {daemon.get_pid()})")
    else:
        console.print("  Status: [yellow]Stopped[/yellow]")
    console.print()

    # Schedule status
    console.print("[bold]Schedule[/bold]")
    console.print(f"  Active Hours: {config.active_hours.start} - {config.active_hours.end}")
    is_active = config.active_hours.is_active_now()
    if is_active:
        console.print("  [green]Currently in active hours[/green]")
    else:
        console.print("  [dim]Outside active hours[/dim]")
    console.print()

    # Usage status
    console.print("[bold]Usage[/bold]")
    limit = config.limits.get_limit_for_today()
    console.print(f"  Limit: {limit}%")

    # Try to get current usage from Claude CLI
    with console.status("[dim]Fetching current usage...[/dim]"):
        usage_info = get_usage_simple()

    if usage_info and usage_info.is_valid():
        # Show session usage
        session_color = "green" if usage_info.session_percent < limit else "red"
        console.print(f"  Session: [{session_color}]{usage_info.session_percent:.0f}%[/{session_color}]")

        # Show weekly usage (used for limit comparison)
        weekly_color = "green" if usage_info.weekly_percent < limit else "red"
        console.print(f"  Weekly:  [{weekly_color}]{usage_info.weekly_percent:.0f}%[/{weekly_color}]")

        if usage_info.weekly_percent >= limit:
            console.print("  [red]⚠ Usage limit exceeded![/red]")
    else:
        console.print("  [dim]Current: Unable to fetch[/dim]")
    console.print()

    # Task status
    console.print("[bold]Tasks[/bold]")
    console.print(f"  Pending:   [yellow]{pending}[/yellow]")
    console.print(f"  Running:   [blue]{running}[/blue]")
    console.print(f"  Completed: [green]{completed}[/green]")
    console.print(f"  Failed:    [red]{failed}[/red]")
    console.print()

    # Today's stats
    today_history = history_storage.get_history()
    if today_history.executions:
        console.print("[bold]Today[/bold]")
        console.print(
            f"  Executed: {today_history.total_completed + today_history.total_failed} "
            f"([green]{today_history.total_completed}[/green] OK, "
            f"[red]{today_history.total_failed}[/red] failed)"
        )
        console.print(f"  Duration: {today_history.total_duration_seconds / SECONDS_PER_MINUTE:.1f} min")


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"scavenger version {__version__}")


if __name__ == "__main__":
    app()
