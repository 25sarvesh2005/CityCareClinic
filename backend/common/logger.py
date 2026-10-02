"""
─────────────────────────────────────────────────────────────────────────────
File        : common/logger.py
Purpose     : Centralized, structured logger for the CityCare Clinic backend.
              Provides a single factory function that every module calls to
              obtain a consistently-configured logger instance.

Responsibilities:
    - Configure log format (UTC timestamp, level, module name, message)
    - Attach both a StreamHandler (console) and a RotatingFileHandler (disk)
    - Expose get_logger() as the sole public API

Used By:
    - common/auth.py
    - core/database/database.py
    - core/controllers/*.py
    - core/cruds/*.py
    - main.py

Returns:
    logging.Logger — A fully configured logger bound to the given name.

Example:
    from common.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Server started")
    logger.error("Something went wrong", exc_info=True)
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# ─── Constants ───────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR: Path = PROJECT_ROOT / "logs"
LOG_FILE: Path = LOG_DIR / "citycare.log"
LOG_FORMAT: str = "[%(asctime)s] [%(levelname)s] [%(name)s] — %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"
MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB per file
BACKUP_COUNT: int = 3  # Keep 3 rotated files


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """
    RotatingFileHandler with safe stream closure and error recovery for Windows file locking.
    Prevents PermissionError [WinError 32] during log rotation.
    """

    def rotate(self, source: str, dest: str) -> None:
        try:
            if self.stream:
                self.stream.close()
                self.stream = None
            super().rotate(source, dest)
        except OSError:
            # On Windows, if file is temporarily locked by another thread or process,
            # suppress the error to keep the application running smoothly.
            pass


# Module-level singleton handlers shared across all named loggers
_console_handler: Optional[logging.Handler] = None
_file_handler: Optional[logging.Handler] = None


def _get_shared_handlers() -> tuple[logging.Handler, logging.Handler]:
    """Initialize and return the shared singleton console and file handlers."""
    global _console_handler, _file_handler

    if _console_handler is not None and _file_handler is not None:
        return _console_handler, _file_handler

    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    formatter.converter = __import__("time").gmtime  # Force UTC timestamps

    # Console handler — INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Rotating file handler — DEBUG and above
    file_handler = WindowsSafeRotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    _console_handler = console_handler
    _file_handler = file_handler

    return _console_handler, _file_handler


def get_logger(module_name: str) -> logging.Logger:
    """
    Return a named logger configured with console and rotating file handlers.

    Creates the logs/ directory if it does not already exist.
    Each module receives its own named logger while sharing the same handlers,
    so log output is unified across the entire application without file contention.

    Args:
        module_name (str): Typically __name__ of the calling module.

    Returns:
        logging.Logger: A configured logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("User registered successfully")
    """
    logger = logging.getLogger(module_name)

    # Prevent duplicate handlers when the same module imports the logger twice
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    console_handler, file_handler = _get_shared_handlers()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Prevent log records from propagating to the root logger
    logger.propagate = False

    return logger
