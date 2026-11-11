"""Data validation module for NSE Market Data Downloader.

Enforces schema validation, non-empty guarantees, required column verification,
duplicate record detection and handling, and preservation of raw market data values.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

import config


class ValidationError(Exception):
    """Base exception for all validation errors."""
    pass


class EmptyDataError(ValidationError):
    """Raised when the retrieved dataset is empty."""
    pass


class MissingColumnsError(ValidationError):
    """Raised when expected columns are missing from the dataset."""
    def __init__(self, message: str, missing_columns: List[str]):
        super().__init__(message)
        self.missing_columns = missing_columns


class InvalidDataFormatError(ValidationError):
    """Raised when the raw data structure is not a list of dictionaries."""
    pass


@dataclass
class ValidationResult:
    """Holds summary metadata from the validation and cleaning process."""
    dataset_key: str
    is_valid: bool
    initial_count: int
    final_count: int
    duplicate_count: int
    columns_found: List[str]
    missing_columns: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DataValidator:
    """Validates and cleans market datasets according to predefined schemas."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initializes the DataValidator.

        Args:
            logger: Application logger instance.
        """
        self.logger = logger or logging.getLogger("NSEMarketDownloader")

    def validate(
        self,
        dataset_key: str,
        raw_records: Any,
        trading_date: str,
    ) -> Tuple[pd.DataFrame, ValidationResult]:
        """Validates and processes raw market records for a given dataset.

        Args:
            dataset_key: The dataset identifier key (e.g. 'top-gainers-losers').
            raw_records: The raw records list returned by the fetcher.
            trading_date: Extracted trading date string ('YYYY-MM-DD').

        Returns:
            Tuple of (cleaned_DataFrame, ValidationResult).

        Raises:
            EmptyDataError: If records list is empty or None.
            InvalidDataFormatError: If records format is invalid.
            MissingColumnsError: If essential required columns are missing.
        """
        self.logger.info(f"Validating dataset '{dataset_key}'...")

        # 1. Type check
        if raw_records is None:
            raise EmptyDataError(
                f"Validation failed for '{dataset_key}': response is None."
            )

        if not isinstance(raw_records, list):
            raise InvalidDataFormatError(
                f"Validation failed for '{dataset_key}': expected list of records, got {type(raw_records).__name__}."
            )

        # 2. Non-empty check
        initial_count = len(raw_records)
        if initial_count == 0:
            raise EmptyDataError(
                f"Validation failed for '{dataset_key}': dataset contains 0 records."
            )

        for idx, item in enumerate(raw_records):
            if not isinstance(item, dict):
                raise InvalidDataFormatError(
                    f"Validation failed for '{dataset_key}': record at index {idx} is not a dictionary."
                )

        # 3. Create DataFrame
        df = pd.DataFrame(raw_records)

        # Standardize known NSE typos across all columns
        if "comapnyName" in df.columns and "companyName" not in df.columns:
            df = df.rename(columns={"comapnyName": "companyName"})

        # 4. Column validation against expected schema
        schema_cfg = config.DATASETS.get(dataset_key, {})
        required_cols = schema_cfg.get("required_columns", [])
        key_cols = schema_cfg.get("key_columns", [])

        cols_present = list(df.columns)
        missing_cols = [req for req in required_cols if req not in cols_present]

        warnings: List[str] = []
        if missing_cols:
            err_msg = (
                f"Validation failed for '{dataset_key}': missing required columns {missing_cols}. "
                f"Available columns: {cols_present}"
            )
            self.logger.error(err_msg)
            raise MissingColumnsError(err_msg, missing_columns=missing_cols)

        # 5. String cleanup: Strip excess whitespace without altering market values
        # e.g. NSE returns 'pChange': '   4.99' in some endpoints
        for col in df.select_dtypes(include=["object", "string"]).columns:
            df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

        # 6. Duplicate record detection & handling
        # Use key_columns if available, else all columns
        subset_cols = [c for c in key_cols if c in df.columns]
        if not subset_cols:
            subset_cols = list(df.columns)

        duplicate_mask = df.duplicated(subset=subset_cols, keep="first")
        duplicate_count = int(duplicate_mask.sum())

        if duplicate_count > 0:
            self.logger.warning(
                f"Dataset '{dataset_key}': Found {duplicate_count} duplicate records based on keys {subset_cols}. "
                "Dropping duplicate entries while preserving original records."
            )
            df = df.drop_duplicates(subset=subset_cols, keep="first").copy()
            warnings.append(f"Dropped {duplicate_count} duplicate records.")

        final_count = len(df)

        # 7. Add trading_date metadata column if not present
        if "trading_date" not in df.columns:
            df["trading_date"] = trading_date

        self.logger.info(
            f"Validation passed for '{dataset_key}': {final_count} valid records "
            f"(Initial: {initial_count}, Duplicates removed: {duplicate_count})."
        )

        val_result = ValidationResult(
            dataset_key=dataset_key,
            is_valid=True,
            initial_count=initial_count,
            final_count=final_count,
            duplicate_count=duplicate_count,
            columns_found=list(df.columns),
            missing_columns=[],
            warnings=warnings,
        )

        return df, val_result
