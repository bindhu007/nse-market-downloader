"""Unit tests for the data validation module (validator.py)."""

import pandas as pd
import pytest

from validator import (
    DataValidator,
    EmptyDataError,
    InvalidDataFormatError,
    MissingColumnsError,
)


class TestDataValidator:
    """Tests for DataValidator logic and schema constraints."""

    @pytest.fixture
    def validator(self):
        return DataValidator()

    def test_validate_top_gainers_losers_success(self, validator):
        raw_data = [
            {
                "symbol": "RELIANCE",
                "series": "EQ",
                "ltp": 2950.5,
                "perChange": 2.4,
                "variation_type": "GAINER",
            },
            {
                "symbol": "INFY",
                "series": "EQ",
                "ltp": 1600.0,
                "perChange": -1.2,
                "variation_type": "LOSER",
            },
        ]
        df, summary = validator.validate("top-gainers-losers", raw_data, "2026-11-11")

        assert summary.is_valid is True
        assert summary.final_count == 2
        assert summary.duplicate_count == 0
        assert "trading_date" in df.columns
        assert df["trading_date"].iloc[0] == "2026-11-11"

    def test_reject_empty_response(self, validator):
        with pytest.raises(EmptyDataError):
            validator.validate("top-gainers-losers", [], "2026-11-11")

        with pytest.raises(EmptyDataError):
            validator.validate("top-gainers-losers", None, "2026-11-11")

    def test_reject_invalid_data_format(self, validator):
        with pytest.raises(InvalidDataFormatError):
            validator.validate("top-gainers-losers", "not a list", "2026-11-11")

        with pytest.raises(InvalidDataFormatError):
            validator.validate("top-gainers-losers", [123, 456], "2026-11-11")

    def test_reject_missing_required_columns(self, validator):
        # Missing 'perChange' and 'variation_type'
        incomplete_data = [
            {
                "symbol": "RELIANCE",
                "series": "EQ",
                "ltp": 2950.5,
            }
        ]
        with pytest.raises(MissingColumnsError) as exc_info:
            validator.validate("top-gainers-losers", incomplete_data, "2026-11-11")

        assert "perChange" in exc_info.value.missing_columns
        assert "variation_type" in exc_info.value.missing_columns

    def test_detect_and_handle_duplicate_records(self, validator):
        data_with_duplicates = [
            {
                "symbol": "TCS",
                "series": "EQ",
                "ltp": 3800.0,
                "perChange": 1.5,
                "variation_type": "GAINER",
            },
            {
                "symbol": "TCS",
                "series": "EQ",
                "ltp": 3800.0,
                "perChange": 1.5,
                "variation_type": "GAINER",
            },
            {
                "symbol": "WIPRO",
                "series": "EQ",
                "ltp": 450.0,
                "perChange": 0.8,
                "variation_type": "GAINER",
            },
        ]
        df, summary = validator.validate("top-gainers-losers", data_with_duplicates, "2026-11-11")

        assert summary.initial_count == 3
        assert summary.final_count == 2
        assert summary.duplicate_count == 1
        assert list(df["symbol"]) == ["TCS", "WIPRO"]

    def test_whitespace_trimming_without_modifying_values(self, validator):
        data = [
            {
                "symbol": " STLTECH ",
                "series": "EQ",
                "ltp": 150.0,
                "change": 7.5,
                "pChange": "   4.99   ",
                "priceBand": "5",
            }
        ]
        df, summary = validator.validate("upper-band-hitters", data, "2026-11-11")

        assert df["symbol"].iloc[0] == "STLTECH"
        assert df["pChange"].iloc[0] == "4.99"
        assert df["ltp"].iloc[0] == 150.0

    def test_typo_column_alias_handling(self, validator):
        # 52W high often has 'comapnyName' typo from NSE
        data = [
            {
                "symbol": "ADANIPORTS",
                "series": "EQ",
                "ltp": 1907.0,
                "pChange": -1.84,
                "new52WHL": 1979.0,
                "comapnyName": "Adani Ports Ltd",
            }
        ]
        df, summary = validator.validate("52-week-high-equity", data, "2026-11-11")
        assert summary.is_valid is True
        assert "companyName" in df.columns
        assert df["companyName"].iloc[0] == "Adani Ports Ltd"

    def test_preserves_original_market_values(self, validator):
        original_price = 1234.56
        data = [
            {
                "symbol": "TATAMOTORS",
                "companyName": "Tata Motors Ltd",
                "volume": "100 L",
                "ltp": original_price,
                "pChange": 3.14,
            }
        ]
        df, summary = validator.validate("volume-gainers-spurts", data, "2026-11-11")
        assert df["ltp"].iloc[0] == original_price
