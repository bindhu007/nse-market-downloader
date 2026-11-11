"""Logging module for NSE Market Data Downloader.

Provides unified, formatted console and file logging for tracking application
runs, dataset downloads, validation steps, storage operations, and errors.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DEFAULT_LOG_DIR


def setup_logger(
    log_dir: Optional[Path] = None,
    log_level: int = logging.INFO,
    trading_date: Optional[str] = None,
) -> logging.Logger:
    """Configures and returns the application logger.

    Args:
        log_dir: Directory where log files are stored. Defaults to logs/.
        log_level: Logging level (e.g. logging.INFO, logging.DEBUG).
        trading_date: Date string (YYYY-MM-DD) for log filename. Defaults to today.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger("NSEMarketDownloader")
    logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logger is invoked multiple times
    if logger.handlers:
        return logger

    target_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    date_str = trading_date or datetime.now().strftime("%Y-%m-%d")
    log_file_path = target_dir / f"nse_downloader_{date_str}.log"

    # Formatter with timestamp, level, module and message
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (UTF-8 encoding)
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.debug(f"Logger initialized. File sink: {log_file_path}")
    return logger
