"""Daemon runner entry point for background execution."""

from scavenger.core.daemon import Daemon


def main() -> None:
    """Start the daemon."""
    daemon = Daemon()
    daemon.start(foreground=False)


if __name__ == "__main__":
    main()
