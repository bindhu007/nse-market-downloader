"""Unit and integration tests for the main orchestrator (main.py)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config
from fetcher import NSEFetchError, NSEFetcher
from main import parse_arguments, run_pipeline
from storage import DataStorage
from validator import DataValidator


class TestMainOrchestration:
    """Tests for CLI arguments, orchestration pipeline, and fault isolation."""

    @pytest.fixture
    def mock_fetcher(self):
        fetcher = MagicMock(spec=NSEFetcher)
        fetcher.fetch_dataset.return_value = (
            [
                {
                    "symbol": "RELIANCE",
                    "series": "EQ",
                    "ltp": 2900,
                    "perChange": 2.5,
                    "change": 50,
                    "pChange": "2.5",
                    "priceBand": "20",
                    "companyName": "Reliance Industries",
                    "volume": "10 L",
                    "new52WHL": 3000,
                    "variation_type": "GAINER",
                }
            ],
            "2026-11-11",
        )
        return fetcher

    def test_parse_arguments_default(self):
        with patch("sys.argv", ["main.py"]):
            args = parse_arguments()
            assert args.dataset == "all"
            assert args.db is False

    def test_parse_arguments_custom(self):
        with patch(
            "sys.argv",
            [
                "main.py",
                "--dataset",
                "top-gainers-losers",
                "--output-dir",
                "custom_out",
                "--db",
                "--date",
                "2026-11-11",
            ],
        ):
            args = parse_arguments()
            assert args.dataset == "top-gainers-losers"
            assert args.output_dir == "custom_out"
            assert args.db is True
            assert args.date == "2026-11-11"

    def test_download_all_four_datasets_success(self, tmp_path, mock_fetcher):
        out_dir = tmp_path / "out"
        log_dir = tmp_path / "logs"

        results = run_pipeline(
            dataset_keys=config.SUPPORTED_DATASET_KEYS,
            output_dir=out_dir,
            log_dir=log_dir,
            fetcher=mock_fetcher,
        )

        assert len(results) == 4
        for key in config.SUPPORTED_DATASET_KEYS:
            assert results[key]["status"] == "SUCCESS"
            assert results[key]["records"] == 1
            assert Path(results[key]["csv_path"]).exists()

    def test_download_individual_dataset(self, tmp_path, mock_fetcher):
        out_dir = tmp_path / "out"
        log_dir = tmp_path / "logs"

        results = run_pipeline(
            dataset_keys=["upper-band-hitters"],
            output_dir=out_dir,
            log_dir=log_dir,
            fetcher=mock_fetcher,
        )

        assert len(results) == 1
        assert "upper-band-hitters" in results
        assert results["upper-band-hitters"]["status"] == "SUCCESS"
        assert Path(results["upper-band-hitters"]["csv_path"]).name == "upper_band_hitters_2026-11-11.csv"

    def test_continue_after_failure_one_dataset(self, tmp_path):
        """Crucial Requirement: If one dataset fails, process the remaining three."""
        out_dir = tmp_path / "out"
        log_dir = tmp_path / "logs"

        mock_fetcher = MagicMock(spec=NSEFetcher)

        def mock_fetch_dispatcher(key):
            if key == "volume-gainers-spurts":
                raise NSEFetchError("Connection reset by peer on volume endpoint")
            return (
                [
                    {
                        "symbol": "INFY",
                        "series": "EQ",
                        "ltp": 1600,
                        "perChange": 1.2,
                        "change": 20,
                        "pChange": "1.2",
                        "priceBand": "20",
                        "new52WHL": 1700,
                        "variation_type": "GAINER",
                    }
                ],
                "2026-11-11",
            )

        mock_fetcher.fetch_dataset.side_effect = mock_fetch_dispatcher

        results = run_pipeline(
            dataset_keys=config.SUPPORTED_DATASET_KEYS,
            output_dir=out_dir,
            log_dir=log_dir,
            fetcher=mock_fetcher,
        )

        assert len(results) == 4
        # Check volume-gainers-spurts failed
        assert results["volume-gainers-spurts"]["status"] == "FAILED"
        assert "Connection reset by peer" in results["volume-gainers-spurts"]["error"]
        assert results["volume-gainers-spurts"]["csv_path"] is None

        # Check other 3 succeeded
        assert results["top-gainers-losers"]["status"] == "SUCCESS"
        assert results["upper-band-hitters"]["status"] == "SUCCESS"
        assert results["52-week-high-equity"]["status"] == "SUCCESS"

        assert Path(results["top-gainers-losers"]["csv_path"]).exists()
        assert Path(results["upper-band-hitters"]["csv_path"]).exists()
        assert Path(results["52-week-high-equity"]["csv_path"]).exists()
