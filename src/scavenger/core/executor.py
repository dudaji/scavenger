"""Claude Code executor for Scavenger."""

import logging
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from scavenger.utils.constants import (
    DEFAULT_TIMEOUT_MINUTES,
    SECONDS_PER_MINUTE,
    SUBPROCESS_TIMEOUT_SECONDS,
)
from scavenger.utils.logging import TaskLogger

logger = logging.getLogger("scavenger.executor")

AUTONOMOUS_RULES = """[Scavenger 자율 실행 모드]
- 이 태스크는 사용자 입력 없이 자동으로 실행됩니다.
- 판단이 필요한 상황에서는 가장 합리적인 선택을 직접 결정하세요.
- 확신이 없는 경우 보수적인 선택을 하세요.
- 작업 불가능한 상황이면 이유를 명시하고 종료하세요.
- 절대로 사용자 입력을 기다리지 마세요.

---

"""


@dataclass
class ExecutionResult:
    """Result of Claude Code execution."""

    success: bool
    output: str
    error: Optional[str] = None
    return_code: int = 0


class ClaudeCodeExecutor:
    """Execute tasks using Claude Code CLI."""

    def __init__(self, claude_path: str = "claude"):
        self.claude_path = claude_path

    def execute(
        self,
        prompt: str,
        working_dir: str,
        timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
        inject_rules: bool = True,
        task_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a task with Claude Code."""
        full_prompt = AUTONOMOUS_RULES + prompt if inject_rules else prompt

        # Setup task logger if task_id provided
        task_logger = TaskLogger(task_id) if task_id else None
        if task_logger:
            task_logger.log_start(prompt, working_dir)

        cmd = [
            self.claude_path,
            "--print",
            "--dangerously-skip-permissions",
            "-p",
            full_prompt,
        ]

        logger.info(f"Executing Claude Code in {working_dir}")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )

            try:
                stdout, stderr = proc.communicate(
                    timeout=timeout_minutes * SECONDS_PER_MINUTE,
                )
            except subprocess.TimeoutExpired:
                # Kill the entire process group to prevent zombie processes
                self._kill_process_group(proc)

                # Clean up pipe buffers to prevent resource leaks
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                try:
                    proc.stderr.close()
                except Exception:
                    pass

                error_msg = f"Task timed out after {timeout_minutes} minutes"
                logger.error(error_msg)
                if task_logger:
                    task_logger.log_complete(False, error_msg)
                return ExecutionResult(
                    success=False,
                    output="",
                    error=error_msg,
                    return_code=-1,
                )

            if task_logger:
                if stdout:
                    task_logger.log_output(stdout)
                if stderr:
                    task_logger.error(f"stderr: {stderr}")

            exec_result = ExecutionResult(
                success=proc.returncode == 0,
                output=stdout,
                error=stderr if proc.returncode != 0 else None,
                return_code=proc.returncode,
            )

            if task_logger:
                task_logger.log_complete(exec_result.success, exec_result.error or "")

            return exec_result
        except FileNotFoundError:
            error_msg = f"Claude Code CLI not found at: {self.claude_path}"
            logger.error(error_msg)
            if task_logger:
                task_logger.log_complete(False, error_msg)
            return ExecutionResult(
                success=False,
                output="",
                error=error_msg,
                return_code=-1,
            )
        except Exception as e:
            error_msg = str(e)
            logger.exception("Unexpected error during execution")
            if task_logger:
                task_logger.log_complete(False, error_msg)
            return ExecutionResult(
                success=False,
                output="",
                error=error_msg,
                return_code=-1,
            )

    @staticmethod
    def _kill_process_group(proc: subprocess.Popen) -> None:
        """Kill a process and its entire process group."""
        try:
            pgid = os.getpgid(proc.pid)
        except (ProcessLookupError, OSError):
            return  # Already dead

        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            return

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.critical(f"Process {proc.pid} survived SIGKILL")

    def check_usage(self) -> Optional[str]:
        """Get current usage from Claude Code /usage command."""
        try:
            result = subprocess.run(
                [self.claude_path, "--print", "-p", "/usage"],
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT_SECONDS,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception:
            return None
