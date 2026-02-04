"""Application-wide constants for Scavenger."""

from pathlib import Path
from typing import Optional

# ============================================================================
# Directory Structure Constants
# ============================================================================

DEFAULT_BASE_DIR_NAME = ".scavenger"
DEFAULT_TASKS_FILE = "tasks.json"
DEFAULT_CONFIG_FILE = "config.json"
HISTORY_SUBDIR = "history"
LOGS_SUBDIR = "logs"
TASK_LOGS_SUBDIR = "logs/tasks"
DAEMON_LOG_FILE = "daemon.log"
MAIN_LOG_FILE = "scavenger.log"
PID_FILE = "scavenger.pid"
WEB_PID_FILE = "web.pid"
WEB_UI_PORT = 8121


def get_base_dir(custom_dir: Optional[Path] = None) -> Path:
    """Get the base Scavenger directory.

    Args:
        custom_dir: Optional custom base directory

    Returns:
        Path to base directory (default: ~/.scavenger)
    """
    return custom_dir or Path.home() / DEFAULT_BASE_DIR_NAME


# ============================================================================
# Time Constants
# ============================================================================

# Conversion constants
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600

# Default timeout for task execution
DEFAULT_TIMEOUT_MINUTES = 30

# Daemon check interval
DEFAULT_CHECK_INTERVAL_SECONDS = 60

# Maximum consecutive errors before pause
MAX_CONSECUTIVE_ERRORS = 5

# Error pause multiplier (wait interval * this)
ERROR_PAUSE_MULTIPLIER = 5

# Daemon stop timeout (seconds to wait for process termination)
DAEMON_STOP_TIMEOUT_SECONDS = 30

# Subprocess timeout for CLI commands (e.g., /usage)
SUBPROCESS_TIMEOUT_SECONDS = 30

# Max wait for task completion during graceful shutdown (30 minutes)
MAX_TASK_WAIT_SECONDS = 30 * SECONDS_PER_MINUTE


# ============================================================================
# Display Constants
# ============================================================================

# Text truncation for prompt display
PROMPT_DISPLAY_MAX = 40
PROMPT_TRUNCATION_AT = 37

# Text truncation for directory display
DIR_DISPLAY_MAX = 30
DIR_TRUNCATION_AT = 27

# Output summary maximum length stored in database
OUTPUT_SUMMARY_MAX_LENGTH = 500

# Report text truncation (plain text format)
REPORT_PROMPT_MAX = 60
REPORT_ERROR_MAX = 100
REPORT_OUTPUT_MAX = 100

# Report HTML truncation (HTML format has more space)
REPORT_PROMPT_HTML_MAX = 200

# Separator line width for reports
SEPARATOR_WIDTH = 60


# ============================================================================
# Logging Constants
# ============================================================================

# Log file rotation settings
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10MB per log file
LOG_FILE_BACKUP_COUNT = 5  # Keep 5 rotated backup files
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ============================================================================
# Default Values
# ============================================================================

# Default days for statistics
DEFAULT_STATS_DAYS = 7

# Default days for log/history retention
DEFAULT_RETENTION_DAYS = 30


# ============================================================================
# Date Formatting
# ============================================================================

ISO_DATE_FORMAT = "%Y-%m-%d"
DATE_FORMAT_EXAMPLE = "2024-01-15"
