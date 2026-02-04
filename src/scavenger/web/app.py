"""Streamlit Web UI for Scavenger."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import streamlit as st

from scavenger.core.config import Config, ConfigStorage
from scavenger.core.daemon import Daemon
from scavenger.core.task import Task, TaskStatus
from scavenger.storage.history import HistoryStorage
from scavenger.storage.json_storage import TaskStorage
from scavenger.utils.cli_helpers import STATUS_COLORS
from scavenger.utils.constants import DEFAULT_STATS_DAYS, SECONDS_PER_MINUTE
from scavenger.utils.usage_parser import get_usage_simple

# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="Scavenger",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Status Color Mapping (Streamlit compatible)
# ============================================================================

# Map TaskStatus to Streamlit-compatible colors/emoji
STATUS_DISPLAY = {
    TaskStatus.PENDING: ("🟡", "orange"),
    TaskStatus.RUNNING: ("🔵", "blue"),
    TaskStatus.COMPLETED: ("🟢", "green"),
    TaskStatus.FAILED: ("🔴", "red"),
    TaskStatus.PAUSED: ("🟣", "violet"),
}


def get_status_display(status: TaskStatus) -> tuple[str, str]:
    """Get emoji and color for status display."""
    return STATUS_DISPLAY.get(status, ("⚪", "gray"))


# ============================================================================
# Session State Management
# ============================================================================


def init_session_state() -> None:
    """Initialize session state with storage instances."""
    if "task_storage" not in st.session_state:
        st.session_state.task_storage = TaskStorage()
    if "config_storage" not in st.session_state:
        st.session_state.config_storage = ConfigStorage()
    if "history_storage" not in st.session_state:
        st.session_state.history_storage = HistoryStorage()
    if "daemon" not in st.session_state:
        st.session_state.daemon = Daemon()


def get_task_storage() -> TaskStorage:
    """Get task storage from session state."""
    return st.session_state.task_storage


def get_config_storage() -> ConfigStorage:
    """Get config storage from session state."""
    return st.session_state.config_storage


def get_history_storage() -> HistoryStorage:
    """Get history storage from session state."""
    return st.session_state.history_storage


def get_daemon() -> Daemon:
    """Get daemon instance from session state."""
    return st.session_state.daemon


# ============================================================================
# Helper Functions
# ============================================================================


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: Optional[float]) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds is None or seconds == 0:
        return "-"

    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis."""
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


# ============================================================================
# Dashboard Page
# ============================================================================


def render_dashboard() -> None:
    """Render the dashboard page."""
    st.header("Dashboard")

    config = get_config_storage().load()
    history_storage = get_history_storage()
    daemon = get_daemon()

    # Top row: Key metrics
    col1, col2, col3, col4 = st.columns(4)

    # Daemon status
    with col1:
        is_running = daemon.is_running()
        if is_running:
            st.metric("Daemon", "Running", delta=f"PID: {daemon.get_pid()}")
        else:
            st.metric("Daemon", "Stopped", delta="Not running", delta_color="off")

    # Usage status
    with col2:
        limit = config.limits.get_limit_for_today()
        usage_info = get_usage_simple()
        if usage_info and usage_info.is_valid():
            weekly_pct = usage_info.weekly_percent
            delta_color = "normal" if weekly_pct < limit else "inverse"
            st.metric(
                "Weekly Usage",
                f"{weekly_pct:.0f}%",
                delta=f"Limit: {limit}% | Session: {usage_info.session_percent:.0f}%",
                delta_color=delta_color,
            )
        else:
            st.metric("Usage Limit", f"{limit}%", delta="Current: N/A")

    # Active hours
    with col3:
        is_active = config.active_hours.is_active_now()
        if is_active:
            st.metric("Schedule", "Active", delta="In active hours")
        else:
            st.metric(
                "Schedule",
                "Inactive",
                delta=f"{config.active_hours.start} - {config.active_hours.end}",
                delta_color="off",
            )

    # Today's executions
    with col4:
        today_history = history_storage.get_history()
        total_today = today_history.total_completed + today_history.total_failed
        st.metric(
            "Today",
            f"{total_today} tasks",
            delta=f"{today_history.total_completed} OK, {today_history.total_failed} failed",
        )

    st.divider()

    # Task summary
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Task Queue")
        tasks = get_task_storage().list_all()

        if not tasks:
            st.info("No tasks in queue")
        else:
            pending = len([t for t in tasks if t.status == TaskStatus.PENDING])
            running = len([t for t in tasks if t.status == TaskStatus.RUNNING])
            completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
            failed = len([t for t in tasks if t.status == TaskStatus.FAILED])

            task_cols = st.columns(4)
            task_cols[0].metric("Pending", pending)
            task_cols[1].metric("Running", running)
            task_cols[2].metric("Completed", completed)
            task_cols[3].metric("Failed", failed)

    with col2:
        st.subheader(f"Statistics (Last {DEFAULT_STATS_DAYS} Days)")
        stats = history_storage.get_stats(days=DEFAULT_STATS_DAYS)

        if stats["total_executions"] == 0:
            st.info("No execution history yet")
        else:
            stat_cols = st.columns(3)
            stat_cols[0].metric("Total Executions", stats["total_executions"])
            stat_cols[1].metric("Success Rate", f"{stats['success_rate']:.1f}%")
            stat_cols[2].metric("Total Duration", f"{stats['total_duration_hours']:.1f}h")

    st.divider()

    # Recent executions
    st.subheader("Recent Executions")
    recent = history_storage.get_recent_history(days=3)

    if not recent or all(len(h.executions) == 0 for h in recent):
        st.info("No recent executions")
    else:
        for history in recent:
            if history.executions:
                with st.expander(
                    f"📅 {history.date} - {history.total_completed + history.total_failed} tasks"
                ):
                    for execution in history.executions[:5]:  # Show last 5 per day
                        emoji, color = get_status_display(execution.status)
                        st.markdown(
                            f"{emoji} **{execution.task_id}**: {truncate_text(execution.prompt, 60)} "
                            f"({format_duration(execution.duration_seconds)})"
                        )


# ============================================================================
# Tasks Page
# ============================================================================


def render_tasks() -> None:
    """Render the tasks page."""
    st.header("Task Management")

    tab1, tab2 = st.tabs(["Task List", "Add Task"])

    with tab1:
        render_task_list()

    with tab2:
        render_add_task_form()


def render_task_list() -> None:
    """Render the task list."""
    task_storage = get_task_storage()
    tasks = task_storage.list_all()

    if not tasks:
        st.info("No tasks found. Add a new task to get started!")
        return

    # Filter options
    col1, col2 = st.columns([1, 3])
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Pending", "Running", "Completed", "Failed", "Paused"],
        )

    # Filter tasks
    if status_filter != "All":
        status_enum = TaskStatus(status_filter.lower())
        tasks = [t for t in tasks if t.status == status_enum]

    # Sort: Running first, then pending by priority, then others
    def sort_key(t: Task) -> tuple:
        status_order = {
            TaskStatus.RUNNING: 0,
            TaskStatus.PENDING: 1,
            TaskStatus.PAUSED: 2,
            TaskStatus.COMPLETED: 3,
            TaskStatus.FAILED: 4,
        }
        return (status_order.get(t.status, 5), t.priority)

    tasks = sorted(tasks, key=sort_key)

    # Display tasks
    for task in tasks:
        emoji, color = get_status_display(task.status)

        with st.container():
            col1, col2, col3, col4, col5, col6 = st.columns([1, 3, 1, 2, 2, 1])

            with col1:
                st.markdown(f"**{task.id}**")
            with col2:
                st.markdown(truncate_text(task.prompt, 50))
            with col3:
                st.markdown(f"P{task.priority}")
            with col4:
                st.markdown(f"{emoji} {task.status.value}")
            with col5:
                st.markdown(f"📁 {truncate_text(task.working_dir, 25)}")
            with col6:
                if task.status in [TaskStatus.PENDING, TaskStatus.PAUSED, TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    if st.button("🗑️", key=f"del_{task.id}", help="Delete task"):
                        try:
                            task_storage.remove(task.id)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete task: {e}")

        st.divider()


def render_add_task_form() -> None:
    """Render the add task form."""
    st.subheader("Add New Task")

    with st.form("add_task_form", clear_on_submit=True):
        prompt = st.text_area(
            "Task Prompt",
            height=150,
            placeholder="Describe the task for Claude Code to execute...",
        )

        col1, col2 = st.columns(2)

        with col1:
            priority = st.slider(
                "Priority",
                min_value=1,
                max_value=10,
                value=5,
                help="1 = highest priority, 10 = lowest priority",
            )

        with col2:
            working_dir = st.text_input(
                "Working Directory",
                value=str(Path.cwd()),
                help="Directory where the task will be executed",
            )

        submitted = st.form_submit_button("Add Task", type="primary")

        if submitted:
            if not prompt.strip():
                st.error("Task prompt cannot be empty")
            elif not Path(working_dir).exists():
                st.error(f"Directory does not exist: {working_dir}")
            else:
                new_task = Task(
                    prompt=prompt.strip(),
                    priority=priority,
                    working_dir=working_dir,
                )
                try:
                    get_task_storage().add(new_task)
                    st.success(f"Task added successfully! ID: {new_task.id}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add task: {e}")


# ============================================================================
# Configuration Page
# ============================================================================


def render_configuration() -> None:
    """Render the configuration page."""
    st.header("Configuration")

    config_storage = get_config_storage()
    config = config_storage.load()

    tab1, tab2, tab3 = st.tabs(["Schedule", "Usage Limits", "Notification"])

    with tab1:
        render_schedule_config(config, config_storage)

    with tab2:
        render_usage_limits_config(config, config_storage)

    with tab3:
        render_notification_config(config)


def render_schedule_config(config: Config, config_storage: ConfigStorage) -> None:
    """Render schedule configuration."""
    st.subheader("Active Hours")

    # Parse time values safely
    try:
        start_value = datetime.strptime(config.active_hours.start, "%H:%M").time()
    except ValueError:
        start_value = datetime.strptime("01:00", "%H:%M").time()

    try:
        end_value = datetime.strptime(config.active_hours.end, "%H:%M").time()
    except ValueError:
        end_value = datetime.strptime("06:00", "%H:%M").time()

    col1, col2 = st.columns(2)

    with col1:
        start_time = st.time_input("Start Time", value=start_value)

    with col2:
        end_time = st.time_input("End Time", value=end_value)

    # Show preview
    is_active = config.active_hours.is_active_now()
    if is_active:
        st.success("Currently in active hours - tasks will be executed")
    else:
        st.info("Currently outside active hours - tasks will wait")

    if st.button("Save Schedule", key="save_schedule"):
        try:
            config.active_hours.start = start_time.strftime("%H:%M")
            config.active_hours.end = end_time.strftime("%H:%M")
            config_storage.save(config)
            st.success("Schedule saved!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save schedule: {e}")


def render_usage_limits_config(config: Config, config_storage: ConfigStorage) -> None:
    """Render usage limits configuration."""
    st.subheader("Daily Usage Limits (%)")

    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    cols = st.columns(7)
    new_limits = {}

    for i, (day, label) in enumerate(zip(days, day_labels)):
        with cols[i]:
            current_value = config.limits.usage_limit_by_day.get(day, config.limits.usage_limit_default)
            new_limits[day] = st.number_input(
                label,
                min_value=0,
                max_value=100,
                value=current_value,
                key=f"limit_{day}",
            )

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        default_limit = st.number_input(
            "Default Limit (%)",
            min_value=0,
            max_value=100,
            value=config.limits.usage_limit_default,
        )

    with col2:
        reset_hour = st.number_input(
            "Usage Reset Hour",
            min_value=0,
            max_value=23,
            value=config.limits.usage_reset_hour,
            help="Hour when daily usage limit resets",
        )

    with col3:
        task_timeout = st.number_input(
            "Task Timeout (minutes)",
            min_value=1,
            max_value=120,
            value=config.limits.task_timeout_minutes,
        )

    if st.button("Save Usage Limits", key="save_limits"):
        try:
            config.limits.usage_limit_by_day = new_limits
            config.limits.usage_limit_default = default_limit
            config.limits.usage_reset_hour = reset_hour
            config.limits.task_timeout_minutes = task_timeout
            config_storage.save(config)
            st.success("Usage limits saved!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save usage limits: {e}")


def render_notification_config(config: Config) -> None:
    """Render notification configuration (read-only view)."""
    st.subheader("Notification Settings")

    st.info("Email notification settings can be configured via CLI:")
    st.code(
        """# Configure email
scavenger config set --email your@email.com
scavenger config set --smtp-host smtp.gmail.com
scavenger config set --smtp-port 587
scavenger config set --smtp-username your@email.com

# Set password environment variable
export SCAVENGER_SMTP_PASSWORD='your-app-password'

# Test configuration
scavenger report test""",
        language="bash",
    )

    st.divider()
    st.subheader("Current Settings")

    if config.notification.email:
        st.write(f"**Email:** {config.notification.email}")
        st.write(f"**SMTP Host:** {config.notification.smtp.host}")
        st.write(f"**SMTP Port:** {config.notification.smtp.port}")
        st.write(f"**Report Time:** {config.notification.report_time}")
    else:
        st.warning("Email notifications not configured")


# ============================================================================
# History Page
# ============================================================================


def render_history() -> None:
    """Render the history page."""
    st.header("Execution History")

    history_storage = get_history_storage()

    # Date selection
    col1, col2 = st.columns([1, 3])

    with col1:
        target_date = st.date_input("Select Date", value=date.today())

    # Load history for selected date
    history = history_storage.get_history(target_date)

    st.divider()

    # Summary for selected date
    st.subheader(f"Summary: {target_date.isoformat()}")

    if history.executions:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total", len(history.executions))
        col2.metric("Completed", history.total_completed)
        col3.metric("Failed", history.total_failed)
        col4.metric("Duration", format_duration(history.total_duration_seconds))

        st.divider()

        # Execution details
        st.subheader("Executions")

        for execution in history.executions:
            emoji, color = get_status_display(execution.status)

            with st.expander(f"{emoji} {execution.task_id}: {truncate_text(execution.prompt, 50)}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown(f"**Status:** {execution.status.value}")
                    st.markdown(f"**Priority:** {execution.priority}")

                with col2:
                    st.markdown(f"**Started:** {format_datetime(execution.started_at)}")
                    st.markdown(f"**Completed:** {format_datetime(execution.completed_at)}")

                with col3:
                    st.markdown(f"**Duration:** {format_duration(execution.duration_seconds)}")
                    st.markdown(f"**Directory:** {truncate_text(execution.working_dir, 30)}")

                st.markdown("**Prompt:**")
                st.text(execution.prompt)

                if execution.error:
                    st.error(f"Error: {execution.error}")

                if execution.output_summary:
                    st.markdown("**Output Summary:**")
                    st.text(execution.output_summary)
    else:
        st.info(f"No executions found for {target_date.isoformat()}")

    st.divider()

    # Aggregated stats
    st.subheader("Aggregated Statistics")

    col1, col2 = st.columns(2)

    with col1:
        days_7 = st.button("Last 7 Days", key="stats_7")
    with col2:
        days_30 = st.button("Last 30 Days", key="stats_30")

    days = 7
    if days_30:
        days = 30

    stats = history_storage.get_stats(days=days)

    if stats["total_executions"] > 0:
        stat_cols = st.columns(5)
        stat_cols[0].metric("Days with Activity", stats["days"])
        stat_cols[1].metric("Total Executions", stats["total_executions"])
        stat_cols[2].metric("Completed", stats["total_completed"])
        stat_cols[3].metric("Failed", stats["total_failed"])
        stat_cols[4].metric("Success Rate", f"{stats['success_rate']:.1f}%")
    else:
        st.info(f"No execution history in the last {days} days")


# ============================================================================
# Sidebar Navigation
# ============================================================================


def render_sidebar() -> str:
    """Render sidebar and return selected page."""
    st.sidebar.title("🔍 Scavenger")
    st.sidebar.markdown("Automated task runner for Claude Code")

    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Tasks", "Configuration", "History"],
        label_visibility="collapsed",
    )

    st.sidebar.divider()

    # Manual refresh
    if st.sidebar.button("🔄 Refresh Now"):
        st.rerun()

    # Daemon status in sidebar
    st.sidebar.divider()
    daemon = get_daemon()
    if daemon.is_running():
        st.sidebar.success(f"Daemon: Running (PID {daemon.get_pid()})")
    else:
        st.sidebar.warning("Daemon: Stopped")

    st.sidebar.caption("Use CLI to start/stop daemon")

    return page


# ============================================================================
# Main App
# ============================================================================


def main() -> None:
    """Main application entry point."""
    init_session_state()

    page = render_sidebar()

    # Route to selected page
    if page == "Dashboard":
        render_dashboard()
    elif page == "Tasks":
        render_tasks()
    elif page == "Configuration":
        render_configuration()
    elif page == "History":
        render_history()


if __name__ == "__main__":
    main()
