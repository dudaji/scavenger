"""Usage parser for Claude Code /usage command.

Runs Claude CLI to get usage information.
"""

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
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
        command = f"{claude_path} /usage"
        home = str(Path.home())
        child = pexpect.spawn(command, encoding="utf-8", timeout=20, cwd=home)

        

        # 데몬(setsid) 환경에서는 workspace trust 프롬프트가 뜰 수 있음
        # trust 프롬프트가 나오면 Enter로 수락 후 진행
        # ANSI 코드가 섞여 있을 수 있으므로 Regex로 처리
        idx = child.expect(["used", "trust.*this.*folder", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        
        if idx == 1:
            # trust 프롬프트 감지됨
            try:
                # "Enter to confirm" 까지 확실히 읽어서 버퍼 비우기
                child.expect(["Enter.*to.*confirm", pexpect.TIMEOUT], timeout=3)
            except:
                pass
            
            # 명시적으로 \r 전송 (Enter)
            child.send("\r")
            
            # trust 수락 후 다시 "used" 대기 (Session Usage가 됨)
            # 이 expect가 성공하면 idx는 0이 됨
            idx = child.expect(["used", pexpect.TIMEOUT, pexpect.EOF], timeout=20)

        # 위에서 idx가 0이면 (바로 잡혔거나 trust 처리 후 잡혔거나) Session Usage 처리
        if idx != 0:
             logger.debug(f"Failed to find session usage 'used' marker (idx={idx})")
             return UsageInfo(session_percent=-1, weekly_percent=-1, raw_output=getattr(child, "before", "") or "")

        # First "used" data is now in child.before/after
        session_raw = child.before + child.after
        session_percent = _extract_usage_percent(session_raw)

        # Second "used" - Weekly Usage
        idx_weekly = child.expect(["used", pexpect.TIMEOUT, pexpect.EOF], timeout=10)
        if idx_weekly != 0:
            logger.debug(f"Failed to find weekly usage 'used' marker (idx={idx_weekly})")
            return UsageInfo(session_percent=session_percent, weekly_percent=-1, raw_output=session_raw + (getattr(child, "before", "") or ""))
            
        weekly_raw = child.before + child.after
        weekly_percent = _extract_usage_percent(weekly_raw)

        return UsageInfo(
            session_percent=session_percent,
            weekly_percent=weekly_percent,
            raw_output=session_raw + weekly_raw,
        )

    except pexpect.TIMEOUT:
        logger.debug("Timeout waiting for Claude CLI response (v2)")
        return UsageInfo(session_percent=-1, weekly_percent=-1, raw_output=getattr(child, "before", "") or "")
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
