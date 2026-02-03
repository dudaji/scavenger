"""Configuration CLI commands for Scavenger."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from scavenger.core.config import ConfigStorage

app = typer.Typer(help="Configuration management commands.")
console = Console()


def get_config_storage() -> ConfigStorage:
    """Get config storage instance."""
    return ConfigStorage()


def parse_usage_limit(value: str) -> dict[str, int]:
    """Parse usage limit string like 'mon:10,tue:20,...'"""
    result = {}
    for item in value.split(","):
        if ":" not in item:
            raise typer.BadParameter(f"Invalid format: {item}. Use 'day:percent' format.")
        day, percent = item.strip().split(":")
        day = day.strip().lower()
        if day not in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            raise typer.BadParameter(f"Invalid day: {day}")
        try:
            result[day] = int(percent.strip())
        except ValueError:
            raise typer.BadParameter(f"Invalid percent: {percent}")
    return result


@app.command("show")
def show_config() -> None:
    """Show current configuration."""
    storage = get_config_storage()
    config = storage.load()

    console.print("[bold]Active Hours[/bold]")
    console.print(f"  Start: {config.active_hours.start}")
    console.print(f"  End: {config.active_hours.end}")
    console.print(f"  Timezone: {config.active_hours.timezone}")
    console.print()

    console.print("[bold]Usage Limits[/bold]")
    table = Table(show_header=True)
    table.add_column("Day")
    table.add_column("Limit %", justify="right")

    days_order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    for day in days_order:
        limit = config.limits.usage_limit_by_day.get(day, config.limits.usage_limit_default)
        table.add_row(day.upper(), str(limit))

    console.print(table)
    console.print(f"  Default: {config.limits.usage_limit_default}%")
    console.print(f"  Reset Hour: {config.limits.usage_reset_hour}:00")
    console.print(f"  Task Timeout: {config.limits.task_timeout_minutes} minutes")
    console.print()

    console.print("[bold]Claude Code[/bold]")
    console.print(f"  Path: {config.claude_code.path}")
    if config.claude_code.extra_args:
        console.print(f"  Extra Args: {' '.join(config.claude_code.extra_args)}")
    console.print()

    console.print("[bold]Notification[/bold]")
    if config.notification.email:
        console.print(f"  Email: {config.notification.email}")
        console.print(f"  SMTP Host: {config.notification.smtp.host}")
        console.print(f"  SMTP Port: {config.notification.smtp.port}")
        console.print(f"  SMTP Username: {config.notification.smtp.username or '[dim]Not set[/dim]'}")
        console.print(f"  Password Env: {config.notification.smtp.password_env}")
        console.print(f"  Report Time: {config.notification.report_time}")
    else:
        console.print("  [dim]Not configured[/dim]")


@app.command("set")
def set_config(
    active_start: Optional[str] = typer.Option(None, "--active-start", help="Active hours start time (HH:MM)"),
    active_end: Optional[str] = typer.Option(None, "--active-end", help="Active hours end time (HH:MM)"),
    usage_limit: Optional[str] = typer.Option(
        None,
        "--usage-limit",
        help="Usage limit by day (e.g., 'mon:10,tue:20,wed:30')",
    ),
    usage_limit_default: Optional[int] = typer.Option(
        None,
        "--usage-limit-default",
        help="Default usage limit percent",
        min=1,
        max=100,
    ),
    usage_reset_hour: Optional[int] = typer.Option(
        None,
        "--usage-reset-hour",
        help="Hour when daily usage resets (0-23)",
        min=0,
        max=23,
    ),
    task_timeout: Optional[int] = typer.Option(
        None,
        "--task-timeout",
        help="Task timeout in minutes",
        min=1,
    ),
    claude_path: Optional[str] = typer.Option(None, "--claude-path", help="Path to Claude Code CLI"),
    email: Optional[str] = typer.Option(None, "--email", help="Email address for notifications"),
    smtp_host: Optional[str] = typer.Option(None, "--smtp-host", help="SMTP server hostname"),
    smtp_port: Optional[int] = typer.Option(None, "--smtp-port", help="SMTP server port"),
    smtp_username: Optional[str] = typer.Option(None, "--smtp-username", help="SMTP username"),
    report_time: Optional[str] = typer.Option(None, "--report-time", help="Daily report time (HH:MM)"),
) -> None:
    """Set configuration values."""
    storage = get_config_storage()
    config = storage.load()
    changed = False

    if active_start:
        config.active_hours.start = active_start
        changed = True

    if active_end:
        config.active_hours.end = active_end
        changed = True

    if usage_limit:
        limits = parse_usage_limit(usage_limit)
        config.limits.usage_limit_by_day.update(limits)
        changed = True

    if usage_limit_default is not None:
        config.limits.usage_limit_default = usage_limit_default
        changed = True

    if usage_reset_hour is not None:
        config.limits.usage_reset_hour = usage_reset_hour
        changed = True

    if task_timeout is not None:
        config.limits.task_timeout_minutes = task_timeout
        changed = True

    if claude_path:
        config.claude_code.path = claude_path
        changed = True

    if email:
        config.notification.email = email
        changed = True

    if smtp_host:
        config.notification.smtp.host = smtp_host
        changed = True

    if smtp_port:
        config.notification.smtp.port = smtp_port
        changed = True

    if smtp_username:
        config.notification.smtp.username = smtp_username
        changed = True

    if report_time:
        config.notification.report_time = report_time
        changed = True

    if changed:
        storage.save(config)
        console.print("[green]Configuration updated.[/green]")
    else:
        console.print("[yellow]No changes specified.[/yellow]")


@app.command("reset")
def reset_config(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Reset configuration to defaults."""
    if not confirm:
        confirm = typer.confirm("Are you sure you want to reset configuration to defaults?")

    if confirm:
        storage = get_config_storage()
        from scavenger.core.config import Config
        storage.save(Config())
        console.print("[green]Configuration reset to defaults.[/green]")
    else:
        console.print("[yellow]Cancelled.[/yellow]")
