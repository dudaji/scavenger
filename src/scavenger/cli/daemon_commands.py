"""Daemon CLI commands for Scavenger."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from scavenger.core.config import ConfigStorage
from scavenger.core.daemon import Daemon
from scavenger.storage.json_storage import TaskStorage
from scavenger.utils.constants import WEB_PID_FILE, WEB_UI_PORT, get_base_dir

app = typer.Typer(help="Daemon management commands.")
console = Console()


def get_daemon() -> Daemon:
    """Get daemon instance."""
    return Daemon()


def get_web_pid_file() -> Path:
    """Get the web UI PID file path."""
    return get_base_dir() / WEB_PID_FILE


def get_web_pid() -> Optional[int]:
    """Get web UI process PID."""
    pid_file = get_web_pid_file()
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def is_web_running() -> bool:
    """Check if web UI is running."""
    pid = get_web_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        # Process doesn't exist, clean up stale PID file
        get_web_pid_file().unlink(missing_ok=True)
        return False


def start_web_ui() -> bool:
    """Start the Streamlit web UI."""
    if is_web_running():
        return True

    web_app_path = Path(__file__).parent.parent / "web" / "app.py"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(web_app_path),
            "--server.port",
            str(WEB_UI_PORT),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Save PID
    get_web_pid_file().write_text(str(proc.pid))

    # Wait a bit and check
    time.sleep(2)
    return is_web_running()


def stop_web_ui() -> bool:
    """Stop the Streamlit web UI."""
    pid = get_web_pid()
    if pid is None:
        return True

    try:
        os.kill(pid, signal.SIGTERM)
        # Wait for termination
        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                break
        get_web_pid_file().unlink(missing_ok=True)
        return True
    except OSError:
        get_web_pid_file().unlink(missing_ok=True)
        return True


@app.command("start")
def start_daemon(
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground (for debugging)"),
    no_web: bool = typer.Option(False, "--no-web", help="Don't start web UI"),
) -> None:
    """Start the scavenger daemon and web UI."""
    daemon = get_daemon()

    if daemon.is_running():
        console.print("[yellow]Daemon is already running.[/yellow]")
        status = daemon.status()
        console.print(f"  PID: {status['pid']}")
        raise typer.Exit(1)

    console.print("[blue]Starting scavenger...[/blue]")

    if foreground:
        console.print("[dim]Running in foreground mode. Press Ctrl+C to stop.[/dim]")
        daemon.start(foreground=True)
    else:
        # Start daemon as subprocess
        proc = subprocess.Popen(
            [sys.executable, "-m", "scavenger.cli.daemon_runner"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait a bit and check if it started
        time.sleep(1)

        if daemon.is_running():
            status = daemon.status()
            console.print(f"[green]Daemon started.[/green]")
            console.print(f"  PID: {status['pid']}")
            console.print(f"  Log: {status['log_file']}")
        else:
            console.print("[red]Failed to start daemon. Check logs for details.[/red]")
            raise typer.Exit(1)

        # Start web UI
        if not no_web:
            console.print("[blue]Starting web UI...[/blue]")
            if start_web_ui():
                console.print(f"[green]Web UI started.[/green]")
                console.print(f"  URL: http://localhost:{WEB_UI_PORT}")
            else:
                console.print("[yellow]Failed to start web UI.[/yellow]")


@app.command("stop")
def stop_daemon(
    force: bool = typer.Option(False, "--force", "-f", help="Force stop (SIGKILL)"),
) -> None:
    """Stop the scavenger daemon and web UI."""
    daemon = get_daemon()

    daemon_was_running = daemon.is_running()
    web_was_running = is_web_running()

    if not daemon_was_running and not web_was_running:
        console.print("[yellow]Scavenger is not running.[/yellow]")
        return

    if force:
        console.print("[red]Force stopping scavenger...[/red]")
    else:
        console.print("[blue]Stopping scavenger...[/blue]")

    # Stop web UI first
    if web_was_running:
        if stop_web_ui():
            console.print("[green]Web UI stopped.[/green]")
        else:
            console.print("[yellow]Failed to stop web UI.[/yellow]")

    # Stop daemon
    if daemon_was_running:
        if daemon.stop(force=force):
            console.print("[green]Daemon stopped.[/green]")
        else:
            console.print("[red]Failed to stop daemon.[/red]")
            raise typer.Exit(1)


@app.command("status")
def daemon_status() -> None:
    """Show daemon and web UI status."""
    daemon = get_daemon()
    status = daemon.status()

    console.print("[bold]Daemon[/bold]")
    if status["running"]:
        console.print(f"  Status: [green]Running[/green] (PID: {status['pid']})")
    else:
        console.print("  Status: [yellow]Stopped[/yellow]")
    console.print(f"  Log File: {status['log_file']}")

    console.print()
    console.print("[bold]Web UI[/bold]")
    if is_web_running():
        console.print(f"  Status: [green]Running[/green] (PID: {get_web_pid()})")
        console.print(f"  URL: http://localhost:{WEB_UI_PORT}")
    else:
        console.print("  Status: [yellow]Stopped[/yellow]")

    # Show config status
    config_storage = ConfigStorage()
    config = config_storage.load()

    console.print()
    console.print("[bold]Schedule[/bold]")
    console.print(f"  Active Hours: {config.active_hours.start} - {config.active_hours.end}")

    is_active = config.active_hours.is_active_now()
    if is_active:
        console.print("  [green]Currently in active hours[/green]")
    else:
        console.print("  [dim]Outside active hours[/dim]")

    # Show usage limit
    console.print()
    console.print("[bold]Usage Limit[/bold]")
    limit = config.limits.get_limit_for_today()
    console.print(f"  Today's Limit: {limit}%")

    # Show task status
    task_storage = TaskStorage()
    tasks = task_storage.list_all()

    from scavenger.core.task import TaskStatus

    pending = len([t for t in tasks if t.status == TaskStatus.PENDING])
    running = len([t for t in tasks if t.status == TaskStatus.RUNNING])

    console.print()
    console.print("[bold]Tasks[/bold]")
    console.print(f"  Pending: {pending}")
    console.print(f"  Running: {running}")


@app.command("logs")
def show_logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """Show daemon logs."""
    daemon = get_daemon()
    log_file = daemon.log_file

    if not log_file.exists():
        console.print("[dim]No logs found.[/dim]")
        return

    if follow:
        import subprocess
        subprocess.run(["tail", "-f", str(log_file)])
    else:
        with open(log_file) as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                console.print(line.rstrip())
