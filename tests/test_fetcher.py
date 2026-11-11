"""Unit tests for the data acquisition module (fetcher.py)."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.exceptions import ConnectionError, Timeout

from fetcher import (
    NSEDataFormatError,
    NSEFetchError,
    NSEFetcher,
    NSEHTTPError,
    NSENetworkError,
    parse_nse_timestamp,
)


class TestTimestampParsing:
    """Tests for the parse_nse_timestamp utility function."""

    def test_parse_standard_nse_timestamp(self):
        ts = "11-Nov-2026 16:00:00"
        result = parse_nse_timestamp(ts)
        assert result == "2026-11-11"

    def test_parse_date_only_nse_timestamp(self):
        ts = "11-Nov-2026"
        result = parse_nse_timestamp(ts)
        assert result == "2026-11-11"

    def test_parse_iso_format(self):
        ts = "2026-11-11"
        result = parse_nse_timestamp(ts)
        assert result == "2026-11-11"

    def test_parse_invalid_or_none_fallback(self):
        result = parse_nse_timestamp(None)
        assert len(result) == 10
        assert result[4] == "-" and result[7] == "-"


class TestNSEFetcher:
    """Tests for NSEFetcher class methods."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.headers = {}
        session.cookies = MagicMock()
        session.cookies.keys.return_value = ["nsit", "AKA_A2"]
        return session

    @pytest.fixture
    def fetcher(self, mock_session):
        return NSEFetcher(
            session=mock_session,
            max_retries=2,
            backoff_factor=0.01,
        )

    def test_initialize_session(self, fetcher, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        fetcher.initialize_session("https://www.nseindia.com")
        mock_session.get.assert_called_once()
        assert fetcher._session_initialized is True

    def test_successful_json_fetch(self, fetcher, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"symbol": "INFY", "ltp": 1500}]}
        mock_session.get.return_value = mock_response

        data = fetcher._get_json_with_retry("https://example.com/api", "https://example.com")
        assert data == {"data": [{"symbol": "INFY", "ltp": 1500}]}

    def test_failed_http_request_404(self, fetcher, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_session.get.return_value = mock_response

        with pytest.raises(NSEHTTPError) as exc_info:
            fetcher._get_json_with_retry("https://example.com/api", "https://example.com")
        assert exc_info.value.status_code == 404

    def test_failed_http_request_500_retries(self, fetcher, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_session.get.return_value = mock_response

        with pytest.raises(NSEHTTPError):
            fetcher._get_json_with_retry("https://example.com/api", "https://example.com")
        assert mock_session.get.call_count == fetcher.max_retries

    def test_connection_timeout(self, fetcher, mock_session):
        mock_session.get.side_effect = Timeout("Request timed out")

        with pytest.raises(NSENetworkError) as exc_info:
            fetcher._get_json_with_retry("https://example.com/api", "https://example.com")
        assert "Connection failed after" in str(exc_info.value)
        assert mock_session.get.call_count == fetcher.max_retries

    def test_connection_error(self, fetcher, mock_session):
        mock_session.get.side_effect = ConnectionError("DNS resolution failed")

        with pytest.raises(NSENetworkError):
            fetcher._get_json_with_retry("https://example.com/api", "https://example.com")

    def test_invalid_json_response_format(self, fetcher, mock_session):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_session.get.return_value = mock_response

        with pytest.raises(NSEDataFormatError):
            fetcher._get_json_with_retry("https://example.com/api", "https://example.com")

    def test_fetch_top_gainers_losers(self, fetcher, mock_session):
        # Mocking responses for both gainers and losers
        mock_g_resp = MagicMock()
        mock_g_resp.status_code = 200
        mock_g_resp.json.return_value = {
            "allSec": {
                "timestamp": "11-Nov-2026 16:00:00",
                "data": [{"symbol": "RELIANCE", "series": "EQ", "ltp": 2900, "perChange": 3.5}],
            }
        }

        mock_l_resp = MagicMock()
        mock_l_resp.status_code = 200
        mock_l_resp.json.return_value = {
            "allSec": {
                "timestamp": "11-Nov-2026 16:00:00",
                "data": [{"symbol": "TCS", "series": "EQ", "ltp": 3800, "perChange": -2.1}],
            }
        }

        mock_session.get.side_effect = [MagicMock(status_code=200), mock_g_resp, mock_l_resp]

        records, trading_date = fetcher.fetch_top_gainers_losers()
        assert len(records) == 2
        assert records[0]["symbol"] == "RELIANCE"
        assert records[0]["variation_type"] == "GAINER"
        assert records[1]["symbol"] == "TCS"
        assert records[1]["variation_type"] == "LOSER"
        assert trading_date == "2026-11-11"

    def test_fetch_upper_band_hitters(self, fetcher, mock_session):
        mock_band_resp = MagicMock()
        mock_band_resp.status_code = 200
        mock_band_resp.json.return_value = {
            "upper": {
                "AllSec": {
                    "timestamp": "11-Nov-2026 16:00:00",
                    "data": [
                        {
                            "symbol": "STLTECH",
                            "series": "EQ",
                            "ltp": 150,
                            "change": 7.5,
                            "pChange": "5.0",
                            "priceBand": "5",
                        }
                    ],
                }
            }
        }
        mock_session.get.side_effect = [MagicMock(status_code=200), mock_band_resp]

        records, trading_date = fetcher.fetch_upper_band_hitters()
        assert len(records) == 1
        assert records[0]["symbol"] == "STLTECH"
        assert trading_date == "2026-11-11"

    def test_fetch_volume_gainers_spurts(self, fetcher, mock_session):
        mock_vol_resp = MagicMock()
        mock_vol_resp.status_code = 200
        mock_vol_resp.json.return_value = {
            "timestamp": "11-Nov-2026 16:00:00",
            "data": [
                {
                    "symbol": "TATAMOTORS",
                    "companyName": "Tata Motors Ltd",
                    "volume": "100 L",
                    "ltp": 950,
                    "pChange": 4.2,
                }
            ],
        }
        mock_session.get.side_effect = [MagicMock(status_code=200), mock_vol_resp]

        records, trading_date = fetcher.fetch_volume_gainers_spurts()
        assert len(records) == 1
        assert records[0]["symbol"] == "TATAMOTORS"
        assert trading_date == "2026-11-11"

    def test_fetch_52_week_high_equity(self, fetcher, mock_session):
        mock_52_resp = MagicMock()
        mock_52_resp.status_code = 200
        mock_52_resp.json.return_value = {
            "timestamp": "11-Nov-2026 16:00:00",
            "data": [
                {
                    "symbol": "HDFCBANK",
                    "series": "EQ",
                    "ltp": 1750,
                    "pChange": 1.5,
                    "new52WHL": 1760,
                }
            ],
        }
        mock_session.get.side_effect = [MagicMock(status_code=200), mock_52_resp]

        records, trading_date = fetcher.fetch_52_week_high_equity()
        assert len(records) == 1
        assert records[0]["symbol"] == "HDFCBANK"
        assert trading_date == "2026-11-11"

    def test_fetch_dataset_dispatcher_unknown_key(self, fetcher):
        with pytest.raises(ValueError) as exc:
            fetcher.fetch_dataset("invalid-dataset-name")
        assert "Unknown dataset" in str(exc.value)
