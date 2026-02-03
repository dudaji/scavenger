"""CLI utilities for formatting and user interaction."""

from datetime import date
from typing import Optional

import typer
from rich.console import Console

from scavenger.core.task import TaskStatus
from scavenger.utils.constants import (
    DATE_FORMAT_EXAMPLE,
    DIR_DISPLAY_MAX,
    DIR_TRUNCATION_AT,
    PROMPT_DISPLAY_MAX,
    PROMPT_TRUNCATION_AT,
)


# ============================================================================
# Status Color Mapping
# ============================================================================

STATUS_COLORS: dict[TaskStatus, str] = {
    TaskStatus.PENDING: "yellow",
    TaskStatus.RUNNING: "blue",
    TaskStatus.COMPLETED: "green",
    TaskStatus.FAILED: "red",
    TaskStatus.PAUSED: "magenta",
}


def get_status_color(status: TaskStatus) -> str:
    """Get Rich color name for a task status.

    Args:
        status: Task status enum value

    Returns:
        Color name string (e.g., "green", "red")
    """
    return STATUS_COLORS.get(status, "white")


def get_status_colors_dict() -> dict[TaskStatus, str]:
    """Get complete status-to-color mapping dictionary.

    Returns:
        Dictionary mapping TaskStatus to color names
    """
    return STATUS_COLORS.copy()


# ============================================================================
# Date Parsing
# ============================================================================


def parse_date_argument(
    date_str: Optional[str],
    console: Console,
) -> date:
    """Parse date argument from CLI with error handling.

    Args:
        date_str: Date string in YYYY-MM-DD format (or None for today)
        console: Rich console for error output

    Returns:
        Parsed date object

    Raises:
        typer.Exit: If date format is invalid
    """
    if not date_str:
        return date.today()

    try:
        return date.fromisoformat(date_str)
    except ValueError:
        print_date_format_error(console, date_str)
        raise typer.Exit(1)


def print_date_format_error(console: Console, date_str: str) -> None:
    """Print standardized date format error message.

    Args:
        console: Rich console for output
        date_str: The invalid date string
    """
    console.print(f"[red]Invalid date format:[/red] {date_str}")
    console.print(f"Use YYYY-MM-DD format (e.g., {DATE_FORMAT_EXAMPLE})")


# ============================================================================
# String Formatting
# ============================================================================


def truncate_prompt(prompt: str) -> str:
    """Truncate prompt for display in tables.

    Args:
        prompt: Full prompt text

    Returns:
        Truncated prompt with ellipsis if needed
    """
    if len(prompt) > PROMPT_DISPLAY_MAX:
        return prompt[:PROMPT_TRUNCATION_AT] + "..."
    return prompt


def truncate_directory(directory: str) -> str:
    """Truncate directory path for display in tables.

    Shows the end of the path with ellipsis prefix.

    Args:
        directory: Full directory path

    Returns:
        Truncated path with ellipsis prefix if needed
    """
    if len(directory) > DIR_DISPLAY_MAX:
        return "..." + directory[-DIR_TRUNCATION_AT:]
    return directory


# ============================================================================
# Email Configuration Guidance
# ============================================================================


def print_email_config_guide(console: Console) -> None:
    """Print email configuration setup instructions.

    Args:
        console: Rich console for output
    """
    console.print("[red]Email is not configured.[/red]")
    console.print()
    console.print("Configure email with:")
    console.print("  scavenger config set --email your@email.com")
    console.print("  scavenger config set --smtp-host smtp.gmail.com")
    console.print("  scavenger config set --smtp-port 587")
    console.print("  scavenger config set --smtp-username your@email.com")
    console.print()
    console.print("Then set the password environment variable:")
    console.print("  export SCAVENGER_SMTP_PASSWORD='your-app-password'")


def print_gmail_app_password_guide(console: Console) -> None:
    """Print Gmail app password setup guide.

    Args:
        console: Rich console for output
    """
    console.print()
    console.print("[yellow]Gmail App Password Guide:[/yellow]")
    console.print()
    console.print("[bold]Step 1:[/bold] Enable 2-Step Verification")
    console.print("  https://myaccount.google.com/security")
    console.print()
    console.print("[bold]Step 2:[/bold] Generate App Password")
    console.print("  https://myaccount.google.com/apppasswords")
    console.print("  - Enter app name (e.g., 'scavenger')")
    console.print("  - Click 'Create'")
    console.print("  - Copy the 16-character password")
    console.print()
    console.print("[bold]Step 3:[/bold] Set Environment Variable")
    console.print("  export SCAVENGER_SMTP_PASSWORD='xxxx xxxx xxxx xxxx'")
    console.print()
