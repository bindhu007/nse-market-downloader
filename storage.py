"""Storage module for NSE Market Data Downloader.

Handles CSV file generation, atomic writes, trading date naming conventions,
duplicate file resolution, and optional SQLite database persistence.
"""

import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional, Union

import pandas as pd

import config


class StorageError(Exception):
    """Raised when writing data to disk or database fails."""
    pass


class DataStorage:
    """Manages persistence of validated market datasets to CSV and SQLite."""

    def __init__(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initializes the DataStorage manager.

        Args:
            output_dir: Custom directory for storing CSV files. Defaults to output/.
            logger: Application logger instance.
        """
        self.output_dir = Path(output_dir) if output_dir else config.DEFAULT_OUTPUT_DIR
        self.logger = logger or logging.getLogger("NSEMarketDownloader")
        self._ensure_output_dir()

    def _ensure_output_dir(self) -> None:
        """Creates the output directory if it does not already exist."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Output directory ensured at: {self.output_dir}")
        except Exception as exc:
            raise StorageError(
                f"Failed to create output directory {self.output_dir}: {exc}"
            ) from exc

    def get_csv_filename(self, dataset_key: str, trading_date: str) -> str:
        """Constructs the canonical CSV filename for a dataset and date.

        Example:
            'top_gainers_losers_2026-11-11.csv'

        Args:
            dataset_key: Dataset identifier (e.g. 'top-gainers-losers').
            trading_date: Trading date string ('YYYY-MM-DD').

        Returns:
            Formatted filename string.
        """
        prefix = config.DATASETS.get(dataset_key, {}).get("file_prefix", dataset_key)
        return f"{prefix}_{trading_date}.csv"

    def save_csv(
        self,
        df: pd.DataFrame,
        dataset_key: str,
        trading_date: str,
        overwrite: bool = True,
    ) -> Path:
        """Saves a pandas DataFrame to a CSV file.

        Uses atomic file replacement to avoid corrupting existing files on same-day reruns.

        Args:
            df: Validated pandas DataFrame to store.
            dataset_key: Dataset identifier.
            trading_date: Trading date ('YYYY-MM-DD').
            overwrite: If True, atomically replaces the file for the same date.
                       If False and file exists, logs a warning and returns existing path.

        Returns:
            Path to the saved CSV file.

        Raises:
            StorageError: If file writing or disk replacement fails.
        """
        filename = self.get_csv_filename(dataset_key, trading_date)
        target_path = self.output_dir / filename

        if target_path.exists():
            if not overwrite:
                self.logger.info(
                    f"File '{filename}' already exists for trading day {trading_date}. "
                    "Skipping overwrite as overwrite=False."
                )
                return target_path
            self.logger.info(
                f"File '{filename}' already exists for trading day {trading_date}. "
                "Safely updating existing file with latest data."
            )

        self._ensure_output_dir()

        # Atomic write: Write to a temporary file in the same filesystem, then replace
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.output_dir,
                delete=False,
                suffix=".tmp",
                encoding="utf-8",
                newline="",
            ) as tmp:
                temp_file = Path(tmp.name)
                df.to_csv(tmp.name, index=False, encoding="utf-8")

            # Atomic replace
            os.replace(temp_file, target_path)
            self.logger.info(
                f"Successfully saved {len(df)} records to CSV: {target_path}"
            )
            return target_path

        except Exception as exc:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            err_msg = f"Failed to save CSV file for '{dataset_key}' at {target_path}: {exc}"
            self.logger.error(err_msg)
            raise StorageError(err_msg) from exc

    def save_to_sqlite(
        self,
        df: pd.DataFrame,
        table_name: str,
        db_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Bonus feature: Persists DataFrame records into an SQLite database table.

        Args:
            df: DataFrame to store.
            table_name: Database table name.
            db_path: Path to the SQLite database file. Defaults to output/nse_market_data.db.

        Returns:
            Path to the database file.

        Raises:
            StorageError: If database write fails.
        """
        target_db = Path(db_path) if db_path else self.output_dir / "nse_market_data.db"
        self._ensure_output_dir()

        try:
            with sqlite3.connect(target_db) as conn:
                # Replace table or append rows based on trading_date
                clean_table = table_name.replace("-", "_")
                df.to_sql(clean_table, conn, if_exists="append", index=False)
                self.logger.info(
                    f"Successfully persisted {len(df)} records into SQLite table '{clean_table}' in {target_db}"
                )
            return target_db
        except Exception as exc:
            err_msg = f"Failed to save to SQLite database {target_db}: {exc}"
            self.logger.error(err_msg)
            raise StorageError(err_msg) from exc
