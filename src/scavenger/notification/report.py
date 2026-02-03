"""Report generation for Scavenger."""

from datetime import date, datetime, timedelta
from typing import Optional

from scavenger.core.task import TaskStatus
from scavenger.storage.history import DailyHistory, HistoryStorage, TaskExecution
from scavenger.utils.constants import (
    REPORT_ERROR_MAX,
    REPORT_OUTPUT_MAX,
    REPORT_PROMPT_MAX,
    REPORT_PROMPT_HTML_MAX,
    SECONDS_PER_MINUTE,
    SEPARATOR_WIDTH,
)


class ReportGenerator:
    """Generate daily reports."""

    def __init__(self, history_storage: Optional[HistoryStorage] = None):
        self.history_storage = history_storage or HistoryStorage()

    def generate_text_report(self, target_date: Optional[date] = None) -> str:
        """Generate a plain text report for a specific date."""
        if target_date is None:
            target_date = date.today()

        history = self.history_storage.get_history(target_date)
        stats = self.history_storage.get_stats(days=7)

        lines = []
        lines.append("=" * SEPARATOR_WIDTH)
        lines.append(f"SCAVENGER DAILY REPORT - {target_date.isoformat()}")
        lines.append("=" * SEPARATOR_WIDTH)
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append(f"  Total Executions: {len(history.executions)}")
        lines.append(f"  Completed: {history.total_completed}")
        lines.append(f"  Failed: {history.total_failed}")

        if history.total_completed + history.total_failed > 0:
            success_rate = history.total_completed / (history.total_completed + history.total_failed) * 100
            lines.append(f"  Success Rate: {success_rate:.1f}%")

        lines.append(f"  Total Duration: {history.total_duration_seconds / SECONDS_PER_MINUTE:.1f} minutes")
        lines.append("")

        # Task Details
        if history.executions:
            lines.append("## Task Details")
            lines.append("-" * SEPARATOR_WIDTH)

            for exec in history.executions:
                status_mark = "✓" if exec.status == TaskStatus.COMPLETED else "✗"
                duration = f"{exec.duration_seconds:.0f}s" if exec.duration_seconds else "-"

                lines.append(f"[{status_mark}] {exec.task_id}")
                lines.append(f"    Status: {exec.status.value}")
                lines.append(f"    Duration: {duration}")
                lines.append(f"    Prompt: {exec.prompt[:REPORT_PROMPT_MAX]}{'...' if len(exec.prompt) > REPORT_PROMPT_MAX else ''}")

                if exec.error:
                    lines.append(f"    Error: {exec.error[:REPORT_ERROR_MAX]}{'...' if len(exec.error) > REPORT_ERROR_MAX else ''}")

                if exec.output_summary:
                    summary = exec.output_summary[:REPORT_OUTPUT_MAX]
                    lines.append(f"    Summary: {summary}{'...' if len(exec.output_summary) > REPORT_OUTPUT_MAX else ''}")

                lines.append("")

        # Weekly Stats
        lines.append("## Weekly Statistics (Last 7 Days)")
        lines.append(f"  Total Executions: {stats['total_executions']}")
        lines.append(f"  Completed: {stats['total_completed']}")
        lines.append(f"  Failed: {stats['total_failed']}")
        lines.append(f"  Success Rate: {stats['success_rate']:.1f}%")
        lines.append(f"  Total Duration: {stats['total_duration_hours']:.1f} hours")
        lines.append("")

        lines.append("=" * SEPARATOR_WIDTH)
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * SEPARATOR_WIDTH)

        return "\n".join(lines)

    def generate_html_report(self, target_date: Optional[date] = None) -> str:
        """Generate an HTML report for a specific date."""
        if target_date is None:
            target_date = date.today()

        history = self.history_storage.get_history(target_date)
        stats = self.history_storage.get_stats(days=7)

        success_rate = 0
        if history.total_completed + history.total_failed > 0:
            success_rate = history.total_completed / (history.total_completed + history.total_failed) * 100

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Scavenger Report - {target_date.isoformat()}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
        }}
        .success {{ color: #4CAF50; }}
        .failure {{ color: #f44336; }}
        .task-list {{
            margin-top: 20px;
        }}
        .task-item {{
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 10px;
        }}
        .task-item.completed {{
            border-left: 4px solid #4CAF50;
        }}
        .task-item.failed {{
            border-left: 4px solid #f44336;
        }}
        .task-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .task-id {{
            font-family: monospace;
            background: #e9ecef;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .task-status {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .task-status.completed {{
            background: #d4edda;
            color: #155724;
        }}
        .task-status.failed {{
            background: #f8d7da;
            color: #721c24;
        }}
        .task-prompt {{
            color: #333;
            margin: 10px 0;
        }}
        .task-meta {{
            font-size: 12px;
            color: #666;
        }}
        .task-error {{
            background: #fff3cd;
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 13px;
        }}
        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Scavenger Daily Report</h1>
        <p style="color: #666;">{target_date.isoformat()}</p>

        <h2>Summary</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{len(history.executions)}</div>
                <div class="stat-label">Total Tasks</div>
            </div>
            <div class="stat-card">
                <div class="stat-value success">{history.total_completed}</div>
                <div class="stat-label">Completed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value failure">{history.total_failed}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{success_rate:.0f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{history.total_duration_seconds / SECONDS_PER_MINUTE:.1f}</div>
                <div class="stat-label">Minutes</div>
            </div>
        </div>

        <h2>Task Details</h2>
        <div class="task-list">
"""

        if history.executions:
            for exec in history.executions:
                status_class = "completed" if exec.status == TaskStatus.COMPLETED else "failed"
                duration = f"{exec.duration_seconds:.0f}s" if exec.duration_seconds else "-"

                html += f"""
            <div class="task-item {status_class}">
                <div class="task-header">
                    <span class="task-id">{exec.task_id}</span>
                    <span class="task-status {status_class}">{exec.status.value.upper()}</span>
                </div>
                <div class="task-prompt">{self._escape_html(exec.prompt[:REPORT_PROMPT_HTML_MAX])}{'...' if len(exec.prompt) > REPORT_PROMPT_HTML_MAX else ''}</div>
                <div class="task-meta">Duration: {duration} | Directory: {exec.working_dir}</div>
"""
                if exec.error:
                    html += f"""
                <div class="task-error">
                    <strong>Error:</strong> {self._escape_html(exec.error[:REPORT_PROMPT_HTML_MAX])}{'...' if len(exec.error) > REPORT_PROMPT_HTML_MAX else ''}
                </div>
"""
                html += "            </div>\n"
        else:
            html += "            <p style='color: #666;'>No tasks executed today.</p>\n"

        html += f"""
        </div>

        <h2>Weekly Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats['total_executions']}</div>
                <div class="stat-label">Total (7 days)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value success">{stats['total_completed']}</div>
                <div class="stat-label">Completed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value failure">{stats['total_failed']}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['success_rate']:.0f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
        </div>

        <div class="footer">
            Generated by Scavenger at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""
        return html

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
