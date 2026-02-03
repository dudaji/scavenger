"""History CLI commands for Scavenger."""

from datetime import date, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from scavenger.core.task import TaskStatus
from scavenger.storage.history import HistoryStorage
from scavenger.utils.cli_helpers import get_status_color, parse_date_argument, truncate_prompt
from scavenger.utils.constants import (
    DEFAULT_RETENTION_DAYS,
    DEFAULT_STATS_DAYS,
    SECONDS_PER_MINUTE,
    SEPARATOR_WIDTH,
)
from scavenger.utils.logging import TaskLogger

app = typer.Typer(help="Execution history commands.")
console = Console()


def get_history_storage() -> HistoryStorage:
    """Get history storage instance."""
    return HistoryStorage()


@app.command("show")
def show_history(
    target_date: Optional[str] = typer.Argument(
        None,
        help="Date to show (YYYY-MM-DD format, default: today)",
    ),
    days: int = typer.Option(1, "--days", "-d", help="Number of days to show"),
) -> None:
    """Show execution history."""
    storage = get_history_storage()

    start_date = parse_date_argument(target_date, console)

    for i in range(days):
        current_date = start_date - timedelta(days=i)
        history = storage.get_history(current_date)

        if not history.executions:
            if days == 1:
                console.print(f"[dim]No executions on {current_date.isoformat()}[/dim]")
            continue

        console.print(f"\n[bold]Date: {current_date.isoformat()}[/bold]")
        console.print(
            f"  Completed: [green]{history.total_completed}[/green] | "
            f"Failed: [red]{history.total_failed}[/red] | "
            f"Duration: {history.total_duration_seconds / SECONDS_PER_MINUTE:.1f} min"
        )

        table = Table()
        table.add_column("Task ID", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Prompt", max_width=40)

        for exec in history.executions:
            status_color = get_status_color(exec.status)
            duration = f"{exec.duration_seconds:.0f}s" if exec.duration_seconds else "-"
            prompt = truncate_prompt(exec.prompt)

            table.add_row(
                exec.task_id,
                f"[{status_color}]{exec.status.value}[/{status_color}]",
                duration,
                prompt,
            )

        console.print(table)


@app.command("stats")
def show_stats(
    days: int = typer.Option(DEFAULT_STATS_DAYS, "--days", "-d", help="Number of days for stats"),
) -> None:
    """Show execution statistics."""
    storage = get_history_storage()
    stats = storage.get_stats(days)

    console.print(f"[bold]Statistics (last {stats['days']} days)[/bold]")
    console.print()
    console.print(f"  Total Executions: {stats['total_executions']}")
    console.print(f"  Completed:        [green]{stats['total_completed']}[/green]")
    console.print(f"  Failed:           [red]{stats['total_failed']}[/red]")
    console.print(f"  Success Rate:     {stats['success_rate']:.1f}%")
    console.print()
    console.print(f"  Total Duration:   {stats['total_duration_hours']:.1f} hours")


@app.command("dates")
def list_dates(
    limit: int = typer.Option(DEFAULT_RETENTION_DAYS, "--limit", "-l", help="Maximum number of dates to show"),
) -> None:
    """List dates with available history."""
    storage = get_history_storage()
    dates = storage.list_available_dates()[:limit]

    if not dates:
        console.print("[dim]No history available.[/dim]")
        return

    console.print("[bold]Available history dates:[/bold]")
    for d in dates:
        history = storage.get_history(d)
        console.print(
            f"  {d.isoformat()} - "
            f"[green]{history.total_completed}[/green] completed, "
            f"[red]{history.total_failed}[/red] failed"
        )


@app.command("task")
def show_task_log(
    task_id: str = typer.Argument(..., help="Task ID to show logs for"),
) -> None:
    """Show detailed log for a specific task."""
    task_logger = TaskLogger(task_id)
    log_content = task_logger.get_log_content()

    if not log_content:
        console.print(f"[dim]No logs found for task {task_id}[/dim]")
        return

    console.print(f"[bold]Task Log: {task_id}[/bold]")
    console.print("-" * SEPARATOR_WIDTH)
    console.print(log_content)


@app.command("clean")
def clean_history(
    days: int = typer.Option(DEFAULT_RETENTION_DAYS, "--days", "-d", help="Keep history for last N days"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Clean old history and task logs."""
    from scavenger.utils.logging import cleanup_old_task_logs

    if not confirm:
        confirm = typer.confirm(f"Delete history and logs older than {days} days?")

    if not confirm:
        console.print("[yellow]Cancelled.[/yellow]")
        return

    # Clean task logs
    removed_logs = cleanup_old_task_logs(days=days)
    console.print(f"[green]Removed {removed_logs} old task log files.[/green]")

    # Clean history files
    storage = get_history_storage()
    cutoff = date.today() - timedelta(days=days)
    removed_history = 0

    for history_date in storage.list_available_dates():
        if history_date < cutoff:
            history_file = storage.history_dir / f"{history_date.isoformat()}.json"
            if history_file.exists():
                history_file.unlink()
                removed_history += 1

    console.print(f"[green]Removed {removed_history} old history files.[/green]")
