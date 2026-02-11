"""Daemon process management for Scavenger."""

import atexit
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from scavenger.core.scheduler import Scheduler
from scavenger.utils.constants import (
    DAEMON_LOG_FILE,
    DAEMON_STOP_TIMEOUT_SECONDS,
    LOGS_SUBDIR,
    PID_FILE,
    get_base_dir,
)

logger = logging.getLogger(__name__)


class Daemon:
    """Daemon process manager."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = get_base_dir(base_dir)
        self.pid_file = self.base_dir / PID_FILE
        self.log_file = self.base_dir / LOGS_SUBDIR / DAEMON_LOG_FILE
        self.scheduler: Optional[Scheduler] = None
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _setup_logging(self) -> None:
        """Setup logging for daemon."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(self.log_file),
            ],
        )

    def _write_pid(self) -> None:
        """Write PID to file."""
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid(self) -> None:
        """Remove PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def get_pid(self) -> Optional[int]:
        """Get daemon PID from file."""
        if not self.pid_file.exists():
            return None
        try:
            with open(self.pid_file) as f:
                return int(f.read().strip())
        except (ValueError, OSError):
            return None

    def is_running(self) -> bool:
        """Check if daemon is running."""
        pid = self.get_pid()
        if pid is None:
            return False

        try:
            os.kill(pid, 0)
            return True
        except OSError:
            # Process doesn't exist, clean up stale PID file
            self._remove_pid()
            return False

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, stopping...")
        if self.scheduler:
            self.scheduler.stop()

    def _handle_reload(self, signum: int, frame) -> None:
        """Handle config reload signal (SIGUSR1)."""
        logger.info("Received config reload signal")
        if self.scheduler:
            self.scheduler.request_config_reload()

    def _daemonize(self) -> None:
        """Daemonize the process using double fork."""
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent exits
                sys.exit(0)
        except OSError as e:
            logger.error(f"First fork failed: {e}")
            sys.exit(1)

        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent exits
                sys.exit(0)
        except OSError as e:
            logger.error(f"Second fork failed: {e}")
            sys.exit(1)

        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        with open(self.log_file, "a") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())

    def start(self, foreground: bool = False) -> bool:
        """Start the daemon.

        Args:
            foreground: If True, run in foreground (for debugging)

        Returns:
            True if started successfully
        """
        if self.is_running():
            logger.warning("Daemon is already running")
            return False

        if not foreground:
            self._daemonize()

        self._setup_logging()
        self._write_pid()
        atexit.register(self._remove_pid)

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        # SIGUSR1 for config reload (Unix only)
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, self._handle_reload)
        else:
            logger.warning("SIGUSR1 not available, config reload signal disabled")

        logger.info(f"Daemon started with PID {os.getpid()}")

        # Start scheduler
        self.scheduler = Scheduler()
        self.scheduler.run_loop()

        return True

    def stop(self, force: bool = False) -> bool:
        """Stop the daemon.

        Args:
            force: If True, send SIGKILL instead of SIGTERM

        Returns:
            True if stopped successfully
        """
        pid = self.get_pid()
        if pid is None:
            logger.info("Daemon is not running")
            return False

        try:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            logger.info(f"Sent signal {sig.name} to PID {pid}")

            # Wait for process to terminate
            import time

            for _ in range(DAEMON_STOP_TIMEOUT_SECONDS):
                try:
                    os.kill(pid, 0)
                    time.sleep(1)
                except OSError:
                    break

            self._remove_pid()
            return True

        except OSError as e:
            logger.error(f"Failed to stop daemon: {e}")
            self._remove_pid()
            return False

    def status(self) -> dict:
        """Get daemon status information."""
        pid = self.get_pid()
        running = self.is_running()

        return {
            "running": running,
            "pid": pid if running else None,
            "pid_file": str(self.pid_file),
            "log_file": str(self.log_file),
        }
