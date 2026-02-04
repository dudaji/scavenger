"""Usage parser for Claude Code /usage command.

Runs Claude CLI to get usage information.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import pexpect

logger = logging.getLogger(__name__)

# ANSI escape code pattern for removing color/control characters
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Pattern to match "XX% used" format
USAGE_PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)%\s*used")


@dataclass
class UsageInfo:
    """Parsed usage information from Claude /usage command.

    Attributes:
        session_percent: Current session usage percentage (-1 if failed to fetch)
        weekly_percent: Weekly usage percentage (-1 if failed to fetch)
        raw_output: Raw output from the command for debugging
    """

    session_percent: float
    weekly_percent: float
    raw_output: str = ""

    def is_within_limit(self, limit_percent: int) -> bool:
        """Check if weekly usage is within the limit.

        Returns False if usage couldn't be fetched (weekly_percent == -1).
        """
        if self.weekly_percent < 0:
            return False
        return self.weekly_percent < limit_percent

    @property
    def percentage(self) -> float:
        """Alias for weekly_percent for backward compatibility."""
        return self.weekly_percent

    def is_valid(self) -> bool:
        """Check if usage info was successfully fetched."""
        return self.session_percent >= 0 and self.weekly_percent >= 0


def _extract_usage_percent(raw_text: str) -> float:
    """Extract usage percentage from text with ANSI codes.

    Args:
        raw_text: Text that may contain ANSI escape codes.

    Returns:
        Extracted percentage (0-100), or -1 if not found or invalid.
    """
    if not raw_text:
        return -1.0

    # Remove ANSI escape codes
    clean_text = ANSI_ESCAPE_PATTERN.sub("", raw_text)

    # Match "XX% used" pattern
    match = USAGE_PERCENT_PATTERN.search(clean_text)
    if match:
        value = float(match.group(1))
        # Validate percentage range
        if 0 <= value <= 100:
            return value

    return -1.0


def get_usage_simple(claude_path: str = "claude") -> Optional[UsageInfo]:
    """Get current usage by running Claude CLI /usage command.

    Runs 'claude /usage' and parses session and weekly usage percentages.

    Args:
        claude_path: Path to Claude CLI executable.

    Returns:
        UsageInfo with session and weekly percentages.
        Returns UsageInfo with -1 values if failed to fetch.
    """
    child = None

    try:
        # Run claude /usage command directly (same as test_usage.py)
        command = f"{claude_path} /usage"
        child = pexpect.spawn(command, encoding="utf-8", timeout=10)

        # First "used" - Session Usage
        child.expect("used")
        session_raw = child.before + child.after
        session_percent = _extract_usage_percent(session_raw)

        # Second "used" - Weekly Usage
        child.expect("used")
        weekly_raw = child.before + child.after
        weekly_percent = _extract_usage_percent(weekly_raw)

        return UsageInfo(
            session_percent=session_percent,
            weekly_percent=weekly_percent,
            raw_output=session_raw + weekly_raw,
        )

    except pexpect.TIMEOUT:
        logger.debug("Timeout waiting for Claude CLI response")
        return UsageInfo(session_percent=-1, weekly_percent=-1, raw_output="")
    except pexpect.EOF:
        logger.debug("Claude CLI process ended unexpectedly")
        return UsageInfo(session_percent=-1, weekly_percent=-1, raw_output="")
    except FileNotFoundError:
        logger.debug(f"Claude CLI not found: {claude_path}")
        return UsageInfo(session_percent=-1, weekly_percent=-1, raw_output="")
    except Exception as e:
        logger.debug(f"Error getting usage: {e}")
        return UsageInfo(session_percent=-1, weekly_percent=-1, raw_output="")
    finally:
        if child:
            child.close()


# Alias for backward compatibility
def get_current_usage(claude_path: str = "claude") -> Optional[UsageInfo]:
    """Alias for get_usage_simple."""
    return get_usage_simple(claude_path)
