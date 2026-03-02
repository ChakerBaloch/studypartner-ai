"""Centralized logging configuration for StudyPartner.

Log files are written to: ~/.studypartner/logs/
Console output uses Rich for colorful, readable logs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from studypartner.shared.constants import LOGS_DIR

# Module-level console for reuse
console = Console()

_initialized = False


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for StudyPartner.

    Args:
        verbose: If True, show DEBUG-level logs in terminal.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    # Create logs directory
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Log file path with date
    log_file = LOGS_DIR / f"studypartner_{datetime.now():%Y-%m-%d}.log"

    # File handler — always DEBUG level, captures everything
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s",
        datefmt="%H:%M:%S",
    ))

    # Console handler — Rich-formatted, respects verbosity
    console_level = logging.DEBUG if verbose else logging.INFO
    console_handler = RichHandler(
        console=console,
        show_path=False,
        show_time=True,
        rich_tracebacks=True,
        markup=True,
        log_time_format="%H:%M:%S",
    )
    console_handler.setLevel(console_level)

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "google", "grpc"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Log startup info
    logger = logging.getLogger("studypartner")
    logger.info("📁 Log file: %s", log_file)
    logger.info("📁 Data dir: %s", LOGS_DIR.parent)
    logger.debug("Verbose logging enabled" if verbose else "Normal logging (use --verbose for debug)")


def get_log_path() -> Path:
    """Get today's log file path."""
    return LOGS_DIR / f"studypartner_{datetime.now():%Y-%m-%d}.log"
