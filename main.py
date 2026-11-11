"""Main entry point and CLI orchestrator for NSE Market Data Downloader.

Coordinates fetching, validation, and storage of NSE market datasets.
Ensures failure in one dataset does not block the remaining downloads.
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import config
from fetcher import NSEFetchError, NSEFetcher
from logger import setup_logger
from storage import DataStorage, StorageError
from validator import DataValidator, ValidationError


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments.

    Returns:
        argparse.Namespace with user options.
    """
    parser = argparse.ArgumentParser(
        description="NSE Market Data Downloader - Automated backend data collection tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py
  python main.py --dataset top-gainers-losers
  python main.py --dataset upper-band-hitters
  python main.py --dataset volume-gainers-spurts
  python main.py --dataset 52-week-high-equity
  python main.py --output-dir custom_output/ --db
""",
    )

    parser.add_argument(
        "--dataset",
        choices=["all"] + config.SUPPORTED_DATASET_KEYS,
        default="all",
        help="Specify which NSE dataset to download (default: all)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(config.DEFAULT_OUTPUT_DIR),
        help=f"Directory to save output CSV files (default: {config.DEFAULT_OUTPUT_DIR})",
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        default=str(config.DEFAULT_LOG_DIR),
        help=f"Directory to save log files (default: {config.DEFAULT_LOG_DIR})",
    )

    parser.add_argument(
        "--db",
        action="store_true",
        help="Bonus feature: Also persist validated data into an SQLite database",
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Override trading date (format: YYYY-MM-DD)",
    )

    return parser.parse_args()


def run_pipeline(
    dataset_keys: List[str],
    output_dir: Path,
    log_dir: Path,
    save_db: bool = False,
    date_override: Optional[str] = None,
    fetcher: Optional[NSEFetcher] = None,
    validator: Optional[DataValidator] = None,
    storage: Optional[DataStorage] = None,
) -> Dict[str, Dict[str, any]]:
    """Executes the data acquisition, validation, and storage pipeline.

    Args:
        dataset_keys: List of dataset keys to process.
        output_dir: Path where CSVs are saved.
        log_dir: Path where logs are saved.
        save_db: Whether to also save to SQLite database.
        date_override: Optional explicit trading date string ('YYYY-MM-DD').
        fetcher: Optional NSEFetcher instance.
        validator: Optional DataValidator instance.
        storage: Optional DataStorage instance.

    Returns:
        Dictionary mapping each dataset key to its execution summary.
    """
    logger = setup_logger(log_dir=log_dir)
    logger.info("=" * 70)
    logger.info("NSE MARKET DATA DOWNLOADER - EXECUTION STARTED")
    logger.info(f"Target datasets: {dataset_keys}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 70)

    # Initialize components
    fetcher = fetcher or NSEFetcher(logger=logger)
    validator = validator or DataValidator(logger=logger)
    storage = storage or DataStorage(output_dir=output_dir, logger=logger)

    results: Dict[str, Dict[str, any]] = {}

    for idx, key in enumerate(dataset_keys, 1):
        meta = config.DATASETS[key]
        display_name = meta["display_name"]
        start_time = time.time()

        print(f"\n[{idx}/{len(dataset_keys)}] Processing: {display_name} ({key})")
        logger.info(f">>> Processing dataset [{idx}/{len(dataset_keys)}]: {display_name}")

        try:
            # Step 1: Fetch
            print(f"    - Fetching data from NSE endpoints...")
            raw_records, fetched_date = fetcher.fetch_dataset(key)
            trading_date = date_override or fetched_date
            print(f"    - Retrieved {len(raw_records)} records for trading date {trading_date}.")

            # Step 2: Validate
            print(f"    - Validating schema, non-empty condition, and duplicates...")
            df, val_summary = validator.validate(key, raw_records, trading_date)
            print(
                f"    - Validation passed: {val_summary.final_count} valid records "
                f"({val_summary.duplicate_count} duplicates removed)."
            )

            # Step 3: Save to CSV
            print(f"    - Saving data to CSV file...")
            csv_path = storage.save_csv(df, key, trading_date)
            print(f"    - CSV generated successfully: {csv_path}")

            # Optional Bonus: Save to SQLite
            if save_db:
                print(f"    - Persisting to SQLite database...")
                db_path = storage.save_to_sqlite(df, key)
                print(f"    - Database updated: {db_path}")

            elapsed = time.time() - start_time
            results[key] = {
                "status": "SUCCESS",
                "display_name": display_name,
                "records": val_summary.final_count,
                "trading_date": trading_date,
                "csv_path": str(csv_path),
                "duration_seconds": round(elapsed, 2),
                "error": None,
            }
            logger.info(
                f"SUCCESS: Dataset '{key}' completed in {elapsed:.2f}s. Saved to {csv_path}"
            )

        except (NSEFetchError, ValidationError, StorageError, Exception) as exc:
            elapsed = time.time() - start_time
            err_msg = str(exc)
            logger.error(
                f"FAILED: Dataset '{key}' encountered an error after {elapsed:.2f}s: {err_msg}",
                exc_info=True,
            )
            print(f"    ! ERROR: Failed to process {display_name}: {err_msg}")
            print(f"    ! Continuing with remaining datasets...")
            results[key] = {
                "status": "FAILED",
                "display_name": display_name,
                "records": 0,
                "trading_date": None,
                "csv_path": None,
                "duration_seconds": round(elapsed, 2),
                "error": err_msg,
            }

    # Print Final Summary Table
    print_execution_summary(results, logger)
    return results


def print_execution_summary(results: Dict[str, Dict[str, any]], logger) -> None:
    """Prints a clear tabular execution summary to console and log."""
    total_datasets = len(results)
    success_count = sum(1 for r in results.values() if r["status"] == "SUCCESS")
    failed_count = total_datasets - success_count

    summary_lines = [
        "",
        "=" * 80,
        f"{'NSE MARKET DATA DOWNLOADER - EXECUTION SUMMARY':^80}",
        "=" * 80,
        f"{'Dataset Name':<32} | {'Status':<9} | {'Records':<8} | {'Duration':<8} | {'Output CSV'}",
        "-" * 80,
    ]

    for key, data in results.items():
        name = data["display_name"][:31]
        status = data["status"]
        rec = str(data["records"])
        dur = f"{data['duration_seconds']}s"
        csv_file = Path(data["csv_path"]).name if data["csv_path"] else "None (Failed)"
        summary_lines.append(
            f"{name:<32} | {status:<9} | {rec:<8} | {dur:<8} | {csv_file}"
        )

    summary_lines.append("-" * 80)
    summary_lines.append(
        f"TOTAL: {total_datasets} | SUCCESSFUL: {success_count} | FAILED: {failed_count}"
    )
    summary_lines.append("=" * 80)

    summary_text = "\n".join(summary_lines)
    print(summary_text)
    logger.info(summary_text)


def main() -> int:
    """CLI entry point.

    Returns:
        0 if all requested datasets succeeded, 1 if any failed.
    """
    args = parse_arguments()

    if args.dataset == "all":
        dataset_keys = config.SUPPORTED_DATASET_KEYS
    else:
        dataset_keys = [args.dataset]

    results = run_pipeline(
        dataset_keys=dataset_keys,
        output_dir=Path(args.output_dir),
        log_dir=Path(args.log_dir),
        save_db=args.db,
        date_override=args.date,
    )

    all_success = all(r["status"] == "SUCCESS" for r in results.values())
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
