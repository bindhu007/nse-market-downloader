"""Unit tests for the storage and persistence module (storage.py)."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from storage import DataStorage, StorageError


class TestDataStorage:
    """Tests for DataStorage persistence functions and edge cases."""

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame(
            [
                {"symbol": "RELIANCE", "ltp": 2900.0, "trading_date": "2026-11-11"},
                {"symbol": "TCS", "ltp": 3800.0, "trading_date": "2026-11-11"},
            ]
        )

    def test_canonical_filename_formatting(self, tmp_path):
        storage = DataStorage(output_dir=tmp_path)
        assert (
            storage.get_csv_filename("top-gainers-losers", "2026-11-11")
            == "top_gainers_losers_2026-11-11.csv"
        )
        assert (
            storage.get_csv_filename("upper-band-hitters", "2026-11-11")
            == "upper_band_hitters_2026-11-11.csv"
        )
        assert (
            storage.get_csv_filename("volume-gainers-spurts", "2026-11-11")
            == "volume_gainers_spurts_2026-11-11.csv"
        )
        assert (
            storage.get_csv_filename("52-week-high-equity", "2026-11-11")
            == "52_week_high_equity_2026-11-11.csv"
        )

    def test_csv_file_creation(self, tmp_path, sample_df):
        storage = DataStorage(output_dir=tmp_path)
        saved_path = storage.save_csv(sample_df, "top-gainers-losers", "2026-11-11")

        assert saved_path.exists()
        assert saved_path.name == "top_gainers_losers_2026-11-11.csv"

        # Verify content with pandas
        read_df = pd.read_csv(saved_path)
        assert len(read_df) == 2
        assert list(read_df["symbol"]) == ["RELIANCE", "TCS"]

    def test_repeated_run_same_trading_day_handling(self, tmp_path, sample_df):
        storage = DataStorage(output_dir=tmp_path)

        # First run
        path1 = storage.save_csv(sample_df, "top-gainers-losers", "2026-11-11")
        assert path1.exists()

        # Second run with updated data
        updated_df = pd.DataFrame(
            [
                {"symbol": "RELIANCE", "ltp": 2950.0, "trading_date": "2026-11-11"},
                {"symbol": "INFY", "ltp": 1600.0, "trading_date": "2026-11-11"},
            ]
        )
        path2 = storage.save_csv(updated_df, "top-gainers-losers", "2026-11-11", overwrite=True)

        assert path1 == path2
        read_df = pd.read_csv(path2)
        assert len(read_df) == 2
        assert read_df["ltp"].iloc[0] == 2950.0

    def test_creates_nested_output_directory(self, tmp_path, sample_df):
        nested_dir = tmp_path / "deeply" / "nested" / "output_dir"
        storage = DataStorage(output_dir=nested_dir)
        saved_path = storage.save_csv(sample_df, "volume-gainers-spurts", "2026-11-11")

        assert nested_dir.exists()
        assert saved_path.exists()

    def test_storage_write_error_handling(self, tmp_path, sample_df):
        storage = DataStorage(output_dir=tmp_path)
        with patch.object(pd.DataFrame, "to_csv", side_effect=PermissionError("Disk write denied")):
            with pytest.raises(StorageError) as exc_info:
                storage.save_csv(sample_df, "top-gainers-losers", "2026-11-11")
            assert "Failed to save CSV file" in str(exc_info.value)

    def test_save_to_sqlite(self, tmp_path, sample_df):
        storage = DataStorage(output_dir=tmp_path)
        db_path = storage.save_to_sqlite(sample_df, "top_gainers_losers")

        assert db_path.exists()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, ltp FROM top_gainers_losers")
            rows = cursor.fetchall()
            assert len(rows) == 2
            assert rows[0] == ("RELIANCE", 2900.0)
