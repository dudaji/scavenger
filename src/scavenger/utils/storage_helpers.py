"""Safe JSON storage utilities with error recovery."""

import json
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("scavenger.storage")


class StorageError(Exception):
    """Base exception for storage operations."""

    pass


class CorruptedFileError(StorageError):
    """JSON file is corrupted and cannot be parsed."""

    pass


def safe_json_load(
    file_path: Path,
    default: Optional[Any] = None,
    backup_corrupted: bool = True,
) -> Any:
    """Safely load JSON from file with error recovery.

    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist or is corrupted.
                 If None and file is corrupted, raises CorruptedFileError.
        backup_corrupted: Whether to backup corrupted files before returning default

    Returns:
        Parsed JSON data or default value

    Raises:
        FileNotFoundError: If file doesn't exist and no default provided
        CorruptedFileError: If file is corrupted and no default provided
    """
    if not file_path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")

        # Backup corrupted file
        if backup_corrupted:
            backup_path = _backup_corrupted_file(file_path)
            logger.warning(f"Backed up corrupted file to: {backup_path}")

        # Return default or raise
        if default is not None:
            logger.info(f"Using default value after JSON error in {file_path}")
            return default
        else:
            raise CorruptedFileError(f"Corrupted JSON file: {file_path}") from e
    except PermissionError as e:
        logger.error(f"Permission denied reading {file_path}: {e}")
        raise StorageError(f"Cannot read {file_path}: permission denied") from e
    except Exception as e:
        logger.exception(f"Unexpected error reading {file_path}: {e}")
        raise StorageError(f"Failed to read {file_path}") from e


def safe_json_save(
    file_path: Path,
    data: Any,
    atomic: bool = True,
    indent: int = 2,
) -> None:
    """Safely save JSON to file with atomic write option.

    Atomic write prevents file corruption by writing to a temporary file first,
    then renaming it to the target path. This ensures the file is either
    completely written or not modified at all.

    Args:
        file_path: Path to JSON file
        data: Data to serialize to JSON
        atomic: Whether to use atomic write (write to temp, then move)
        indent: JSON indentation level

    Raises:
        StorageError: If write operation fails
    """
    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if atomic:
            # Write to temporary file first, then atomic rename
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=file_path.parent,
                delete=False,
                suffix=".tmp",
            ) as tmp_file:
                json.dump(data, tmp_file, indent=indent, default=str)
                tmp_path = Path(tmp_file.name)

            # Atomic move (overwrites destination)
            shutil.move(str(tmp_path), str(file_path))
            logger.debug(f"Atomically saved JSON to {file_path}")
        else:
            # Direct write
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, default=str)
            logger.debug(f"Saved JSON to {file_path}")

    except PermissionError as e:
        logger.error(f"Permission denied writing {file_path}: {e}")
        raise StorageError(f"Cannot write {file_path}: permission denied") from e
    except OSError as e:
        logger.error(f"OS error writing {file_path}: {e}")
        raise StorageError(f"Failed to write {file_path}: {e}") from e
    except Exception as e:
        logger.exception(f"Failed to save JSON to {file_path}: {e}")
        raise StorageError(f"Failed to write {file_path}") from e


def _backup_corrupted_file(file_path: Path) -> Path:
    """Backup a corrupted file with timestamp.

    Args:
        file_path: Path to file to backup

    Returns:
        Path to backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f".corrupted.{timestamp}{file_path.suffix}")
    try:
        shutil.copy2(file_path, backup_path)
    except Exception as e:
        logger.warning(f"Failed to backup corrupted file: {e}")
        # Don't raise - backup is best-effort
    return backup_path
