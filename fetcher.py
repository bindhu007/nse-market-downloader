"""Data acquisition module for NSE Market Data Downloader.

Implements robust HTTP fetching with session cookie management,
exponential backoff retries, error handling, and dedicated extraction
logic for all four NSE market datasets.
"""

import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

import config


class NSEFetchError(Exception):
    """Base exception for all NSE fetching errors."""
    pass


class NSENetworkError(NSEFetchError):
    """Raised when network connectivity or connection fails."""
    pass


class NSEHTTPError(NSEFetchError):
    """Raised when an HTTP error status code is encountered."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class NSEDataFormatError(NSEFetchError):
    """Raised when the received response format is unexpected or malformed."""
    pass


def parse_nse_timestamp(timestamp_str: Optional[str]) -> str:
    """Parses an NSE timestamp string into ISO standard YYYY-MM-DD.

    Args:
        timestamp_str: Raw timestamp string from NSE response (e.g. '11-Nov-2026 16:00:00').

    Returns:
        Formatted date string 'YYYY-MM-DD'. Defaults to today's date if parsing fails.
    """
    if not timestamp_str or not isinstance(timestamp_str, str):
        return datetime.now().strftime("%Y-%m-%d")

    clean_ts = timestamp_str.strip()
    formats_to_try = [
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats_to_try:
        try:
            parsed = datetime.strptime(clean_ts, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try matching first part before whitespace
    first_part = clean_ts.split()[0] if " " in clean_ts else clean_ts
    for fmt in ["%d-%b-%Y", "%Y-%m-%d"]:
        try:
            parsed = datetime.strptime(first_part, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return datetime.now().strftime("%Y-%m-%d")


class NSEFetcher:
    """Manages HTTP requests and data retrieval for NSE market datasets."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        timeout: int = config.REQUEST_TIMEOUT,
        max_retries: int = config.MAX_RETRIES,
        backoff_factor: float = config.BACKOFF_FACTOR,
        session: Optional[requests.Session] = None,
    ):
        """Initializes the NSEFetcher.

        Args:
            logger: Application logger instance.
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of retry attempts per request.
            backoff_factor: Exponential backoff delay multiplier.
            session: Optional pre-configured requests.Session (useful for testing/mocking).
        """
        self.logger = logger or logging.getLogger("NSEMarketDownloader")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = session or requests.Session()
        if hasattr(self.session, "headers") and hasattr(self.session.headers, "update"):
            self.session.headers.update(config.DEFAULT_HEADERS)
        self._session_initialized = False

    def initialize_session(self, referer_url: str = config.NSE_BASE_URL) -> None:
        """Establishes initial session cookies required by NSE India endpoints.

        Args:
            referer_url: URL to visit to acquire session cookies.

        Raises:
            NSENetworkError: If the initial handshake fails.
        """
        self.logger.info(f"Initializing NSE session via {referer_url}...")
        try:
            response = self.session.get(
                referer_url,
                headers=config.DEFAULT_HEADERS,
                timeout=self.timeout,
            )
            response.raise_for_status()
            self._session_initialized = True
            cookies = list(self.session.cookies.keys()) if hasattr(self.session, "cookies") else []
            self.logger.info(
                f"Session initialized successfully. Cookies obtained: {cookies}"
            )
        except (Timeout, ConnectionError) as exc:
            self.logger.warning(
                f"Initial session handshake warning: {exc}. Will proceed with API calls."
            )
        except Exception as exc:
            self.logger.warning(
                f"Session initialization encountered: {exc}. Will proceed."
            )

    def _get_json_with_retry(
        self,
        endpoint_url: str,
        referer_url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Performs a GET request expecting JSON with exponential backoff retries.

        Args:
            endpoint_url: The API endpoint URL.
            referer_url: The referer webpage URL.
            params: Optional query parameters.

        Returns:
            Decoded JSON dictionary or list from the response.

        Raises:
            NSENetworkError: If network connectivity or timeout fails all retries.
            NSEHTTPError: If HTTP error occurs (e.g. 403, 404, 500).
            NSEDataFormatError: If the response is not valid JSON.
        """
        request_headers = dict(config.API_HEADERS)
        request_headers["Referer"] = referer_url

        last_exception: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(
                    f"Fetching {endpoint_url} (Attempt {attempt}/{self.max_retries})..."
                )
                response = self.session.get(
                    endpoint_url,
                    headers=request_headers,
                    params=params,
                    timeout=self.timeout,
                )

                if response.status_code == 401 or response.status_code == 403:
                    # Cookie might be expired, attempt to refresh session once
                    self.logger.warning(
                        f"Received HTTP {response.status_code}. Refreshing session cookies..."
                    )
                    self.initialize_session(referer_url)
                    response = self.session.get(
                        endpoint_url,
                        headers=request_headers,
                        params=params,
                        timeout=self.timeout,
                    )

                if response.status_code != 200:
                    raise NSEHTTPError(
                        f"HTTP {response.status_code} for {endpoint_url}: {response.text[:200]}",
                        status_code=response.status_code,
                    )

                try:
                    data = response.json()
                    return data
                except ValueError as json_err:
                    raise NSEDataFormatError(
                        f"Failed to parse JSON response from {endpoint_url}: {json_err}"
                    ) from json_err

            except (Timeout, ConnectionError) as net_err:
                last_exception = net_err
                wait_time = (self.backoff_factor ** attempt) + random.uniform(0.1, 0.5)
                self.logger.warning(
                    f"Network error on attempt {attempt}/{self.max_retries} for {endpoint_url}: {net_err}. "
                    f"Retrying in {wait_time:.2f}s..."
                )
                time.sleep(wait_time)

            except NSEHTTPError as http_err:
                # Do not retry on 404 client errors
                if http_err.status_code == 404:
                    raise
                last_exception = http_err
                wait_time = (self.backoff_factor ** attempt) + random.uniform(0.1, 0.5)
                self.logger.warning(
                    f"HTTP error on attempt {attempt}/{self.max_retries} for {endpoint_url}: {http_err}. "
                    f"Retrying in {wait_time:.2f}s..."
                )
                time.sleep(wait_time)

            except Exception as exc:
                last_exception = exc
                break

        if isinstance(last_exception, (Timeout, ConnectionError)):
            raise NSENetworkError(
                f"Connection failed after {self.max_retries} attempts for {endpoint_url}: {last_exception}"
            ) from last_exception
        elif isinstance(last_exception, NSEHTTPError):
            raise last_exception
        elif isinstance(last_exception, NSEDataFormatError):
            raise last_exception
        else:
            raise NSEFetchError(
                f"Failed to fetch data from {endpoint_url}: {last_exception}"
            )

    def fetch_top_gainers_losers(self) -> Tuple[List[Dict[str, Any]], str]:
        """Fetches Dataset 1: Top Gainers and Losers from NSE.

        Returns:
            Tuple of (records_list, trading_date_str).

        Raises:
            NSEFetchError: If data retrieval fails.
        """
        webpage_url = config.WEBPAGE_URLS["top-gainers-losers"]
        gainers_url = config.API_ENDPOINTS["top-gainers"]
        losers_url = config.API_ENDPOINTS["top-losers"]

        # Ensure session is ready
        if not self._session_initialized:
            self.initialize_session(webpage_url)

        self.logger.info("Fetching Top Gainers data...")
        gainers_resp = self._get_json_with_retry(gainers_url, referer_url=webpage_url)

        self.logger.info("Fetching Top Losers data...")
        losers_resp = self._get_json_with_retry(losers_url, referer_url=webpage_url)

        records: List[Dict[str, Any]] = []
        raw_timestamp: Optional[str] = None

        # Process Gainers
        if isinstance(gainers_resp, dict):
            # Prefer 'allSec', fallback to 'NIFTY'
            g_sec = gainers_resp.get("allSec") or gainers_resp.get("NIFTY") or {}
            raw_timestamp = g_sec.get("timestamp") or gainers_resp.get("timestamp")
            g_data = g_sec.get("data", [])
            for item in g_data:
                if isinstance(item, dict):
                    row = dict(item)
                    row["variation_type"] = "GAINER"
                    records.append(row)

        # Process Losers
        if isinstance(losers_resp, dict):
            l_sec = losers_resp.get("allSec") or losers_resp.get("NIFTY") or {}
            if not raw_timestamp:
                raw_timestamp = l_sec.get("timestamp") or losers_resp.get("timestamp")
            l_data = l_sec.get("data", [])
            for item in l_data:
                if isinstance(item, dict):
                    row = dict(item)
                    row["variation_type"] = "LOSER"
                    records.append(row)

        trading_date = parse_nse_timestamp(raw_timestamp)
        self.logger.info(
            f"Top Gainers / Losers: Retrieved {len(records)} records for trading date {trading_date}."
        )
        return records, trading_date

    def fetch_upper_band_hitters(self) -> Tuple[List[Dict[str, Any]], str]:
        """Fetches Dataset 2: Upper Band Hitters from NSE.

        Returns:
            Tuple of (records_list, trading_date_str).

        Raises:
            NSEFetchError: If data retrieval fails.
        """
        webpage_url = config.WEBPAGE_URLS["upper-band-hitters"]
        api_url = config.API_ENDPOINTS["upper-band-hitters"]

        if not self._session_initialized:
            self.initialize_session(webpage_url)

        self.logger.info("Fetching Upper Band Hitters data...")
        response_data = self._get_json_with_retry(api_url, referer_url=webpage_url)

        records: List[Dict[str, Any]] = []
        raw_timestamp: Optional[str] = None

        if isinstance(response_data, dict):
            upper_section = response_data.get("upper", {})
            if isinstance(upper_section, dict):
                # Prefer 'AllSec', fallback to combining 'SecGtr20' and 'SecLwr20'
                all_sec = upper_section.get("AllSec")
                if isinstance(all_sec, dict):
                    raw_timestamp = all_sec.get("timestamp")
                    records = all_sec.get("data", [])
                else:
                    # Fallback to combining sub-categories
                    gtr = upper_section.get("SecGtr20", {}).get("data", [])
                    lwr = upper_section.get("SecLwr20", {}).get("data", [])
                    raw_timestamp = upper_section.get("SecGtr20", {}).get("timestamp")
                    records = list(gtr) + list(lwr)

        trading_date = parse_nse_timestamp(raw_timestamp)
        self.logger.info(
            f"Upper Band Hitters: Retrieved {len(records)} records for trading date {trading_date}."
        )
        return records, trading_date

    def fetch_volume_gainers_spurts(self) -> Tuple[List[Dict[str, Any]], str]:
        """Fetches Dataset 3: Volume Gainers / Spurts from NSE.

        Returns:
            Tuple of (records_list, trading_date_str).

        Raises:
            NSEFetchError: If data retrieval fails.
        """
        webpage_url = config.WEBPAGE_URLS["volume-gainers-spurts"]
        api_url = config.API_ENDPOINTS["volume-gainers-spurts"]

        if not self._session_initialized:
            self.initialize_session(webpage_url)

        self.logger.info("Fetching Volume Gainers / Spurts data...")
        response_data = self._get_json_with_retry(api_url, referer_url=webpage_url)

        records: List[Dict[str, Any]] = []
        raw_timestamp: Optional[str] = None

        if isinstance(response_data, dict):
            raw_timestamp = response_data.get("timestamp")
            records = response_data.get("data", [])
        elif isinstance(response_data, list):
            records = response_data

        trading_date = parse_nse_timestamp(raw_timestamp)
        self.logger.info(
            f"Volume Gainers / Spurts: Retrieved {len(records)} records for trading date {trading_date}."
        )
        return records, trading_date

    def fetch_52_week_high_equity(self) -> Tuple[List[Dict[str, Any]], str]:
        """Fetches Dataset 4: 52-Week High Equity Market from NSE.

        Returns:
            Tuple of (records_list, trading_date_str).

        Raises:
            NSEFetchError: If data retrieval fails.
        """
        webpage_url = config.WEBPAGE_URLS["52-week-high-equity"]
        api_url = config.API_ENDPOINTS["52-week-high-equity"]

        if not self._session_initialized:
            self.initialize_session(webpage_url)

        self.logger.info("Fetching 52-Week High Equity data...")
        response_data = self._get_json_with_retry(api_url, referer_url=webpage_url)

        records: List[Dict[str, Any]] = []
        raw_timestamp: Optional[str] = None

        if isinstance(response_data, dict):
            raw_timestamp = response_data.get("timestamp")
            records = response_data.get("data", [])
        elif isinstance(response_data, list):
            records = response_data

        trading_date = parse_nse_timestamp(raw_timestamp)
        self.logger.info(
            f"52-Week High Equity: Retrieved {len(records)} records for trading date {trading_date}."
        )
        return records, trading_date

    def fetch_dataset(self, dataset_key: str) -> Tuple[List[Dict[str, Any]], str]:
        """Generic dispatcher to fetch a dataset by key.

        Args:
            dataset_key: One of the supported dataset keys.

        Returns:
            Tuple of (records_list, trading_date_str).

        Raises:
            ValueError: If dataset_key is unknown.
            NSEFetchError: If data fetching fails.
        """
        dispatch_map = {
            "top-gainers-losers": self.fetch_top_gainers_losers,
            "upper-band-hitters": self.fetch_upper_band_hitters,
            "volume-gainers-spurts": self.fetch_volume_gainers_spurts,
            "52-week-high-equity": self.fetch_52_week_high_equity,
        }

        if dataset_key not in dispatch_map:
            raise ValueError(
                f"Unknown dataset '{dataset_key}'. Supported: {list(dispatch_map.keys())}"
            )

        return dispatch_map[dataset_key]()
