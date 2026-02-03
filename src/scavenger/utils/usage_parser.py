"""Usage parser for Claude Code /usage command.

Runs Claude CLI interactively to get usage information.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import pexpect

logger = logging.getLogger(__name__)

# Pattern to match usage lines like "claude-opus-4-5: 20%" or "Opus: 20%"
USAGE_LINE_PATTERN = re.compile(r"([a-zA-Z0-9_-]+):\s*(\d+(?:\.\d+)?)\s*%")


@dataclass
class UsageInfo:
    """Parsed usage information from Claude /usage command."""

    percentage: float
    raw_output: str
    model_usages: dict[str, float] = field(default_factory=dict)

    def is_within_limit(self, limit_percent: int) -> bool:
        """Check if current usage is within the limit."""
        return self.percentage < limit_percent

    def get_max_usage(self) -> float:
        """Get the maximum usage percentage across all models."""
        if self.model_usages:
            return max(self.model_usages.values())
        return self.percentage


def parse_usage_output(output: str) -> Optional[UsageInfo]:
    """Parse Claude /usage output to extract percentages.

    Expected format:
        claude-opus-4-5: 20%
        claude-sonnet-4-5: 29%
        claude-haiku-4-5: 18%
    """
    if not output:
        return None

    model_usages: dict[str, float] = {}

    for match in USAGE_LINE_PATTERN.finditer(output):
        name = match.group(1)
        percentage = float(match.group(2))
        model_usages[name] = percentage

    if model_usages:
        return UsageInfo(
            percentage=max(model_usages.values()),
            raw_output=output,
            model_usages=model_usages,
        )

    return None


def get_usage_simple(claude_path: str = "claude") -> Optional[UsageInfo]:
    """Get current usage by running Claude CLI /usage command.

    Starts Claude in interactive mode, sends /usage, captures output, then exits.

    Args:
        claude_path: Path to Claude CLI executable.

    Returns:
        UsageInfo with usage percentages, or None if failed.
    """
    try:
        # Start Claude CLI
        child = pexpect.spawn(
            claude_path,
            encoding="utf-8",
            timeout=30,
        )

        # Wait for Claude to be ready (look for prompt or just wait)
        try:
            child.expect([r"[>›]", r"\n"], timeout=10)
        except pexpect.TIMEOUT:
            pass

        # Send /usage command
        child.sendline("/usage")

        # Collect output until we see percentages or timeout
        output_buffer = []
        try:
            # Read output for a few seconds
            while True:
                index = child.expect([r"\d+%", pexpect.TIMEOUT, pexpect.EOF], timeout=5)
                if index == 0:
                    # Found a percentage, capture context
                    output_buffer.append(child.before + child.after)
                else:
                    break
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass

        # Exit cleanly
        try:
            child.sendline("/exit")
            child.expect(pexpect.EOF, timeout=5)
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
        finally:
            child.close()

        # Parse collected output
        full_output = "".join(output_buffer)
        if full_output:
            return parse_usage_output(full_output)

        return None

    except pexpect.exceptions.ExceptionPexpect as e:
        logger.debug(f"pexpect error: {e}")
        return None
    except FileNotFoundError:
        logger.debug(f"Claude CLI not found: {claude_path}")
        return None
    except Exception as e:
        logger.debug(f"Error getting usage: {e}")
        return None


# Alias for backward compatibility
def get_current_usage(claude_path: str = "claude") -> Optional[UsageInfo]:
    """Alias for get_usage_simple."""
    return get_usage_simple(claude_path)
