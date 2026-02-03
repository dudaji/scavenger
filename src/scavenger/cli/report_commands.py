"""Report CLI commands for Scavenger."""

from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from scavenger.notification.email import EmailSender
from scavenger.notification.report import ReportGenerator
from scavenger.utils.cli_helpers import (
    parse_date_argument,
    print_email_config_guide,
    print_gmail_app_password_guide,
)

app = typer.Typer(help="Report generation and email commands.")
console = Console()


@app.command("generate")
def generate_report(
    target_date: Optional[str] = typer.Argument(
        None,
        help="Date for report (YYYY-MM-DD format, default: today)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: print to console)",
    ),
    html: bool = typer.Option(False, "--html", help="Generate HTML format"),
) -> None:
    """Generate a report for a specific date."""
    report_date = parse_date_argument(target_date, console)

    generator = ReportGenerator()

    if html:
        report = generator.generate_html_report(report_date)
    else:
        report = generator.generate_text_report(report_date)

    if output:
        output_path = Path(output)
        output_path.write_text(report)
        console.print(f"[green]Report saved to:[/green] {output_path}")
    else:
        console.print(report)


@app.command("send")
def send_report(
    target_date: Optional[str] = typer.Argument(
        None,
        help="Date for report (YYYY-MM-DD format, default: today)",
    ),
) -> None:
    """Send a report via email."""
    report_date = parse_date_argument(target_date, console)

    sender = EmailSender()

    if not sender.is_configured():
        print_email_config_guide(console)
        raise typer.Exit(1)

    console.print(f"[blue]Sending report for {report_date.isoformat()}...[/blue]")

    result = sender.send_daily_report(report_date)

    if result.success:
        console.print(f"[green]{result.message}[/green]")
    else:
        console.print(f"[red]Failed:[/red] {result.message}")
        raise typer.Exit(1)


@app.command("test")
def test_email() -> None:
    """Send a test email to verify configuration."""
    sender = EmailSender()

    if not sender.is_configured():
        print_email_config_guide(console)
        raise typer.Exit(1)

    console.print("[blue]Sending test email...[/blue]")

    result = sender.send_test_email()

    if result.success:
        console.print(f"[green]{result.message}[/green]")
    else:
        console.print(f"[red]Failed:[/red] {result.message}")

        # Show Gmail app password guide if authentication failed
        if "authentication failed" in result.message.lower():
            print_gmail_app_password_guide(console)

        raise typer.Exit(1)


@app.command("preview")
def preview_report(
    target_date: Optional[str] = typer.Argument(
        None,
        help="Date for report (YYYY-MM-DD format, default: today)",
    ),
) -> None:
    """Preview the HTML report in a browser."""
    import tempfile
    import webbrowser

    report_date = parse_date_argument(target_date, console)

    generator = ReportGenerator()
    html = generator.generate_html_report(report_date)

    # Write to temp file and open in browser
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(html)
        temp_path = f.name

    console.print("[blue]Opening report in browser...[/blue]")
    webbrowser.open(f"file://{temp_path}")
    console.print(f"[dim]Temp file: {temp_path}[/dim]")
