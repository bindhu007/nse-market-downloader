"""Configuration module for NSE Market Data Downloader.

Stores NSE URLs, dataset definitions, request headers, timeouts,
retry parameters, and validation schema expectations.
"""

import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"

# NSE URLs
NSE_BASE_URL = "https://www.nseindia.com"

# Webpage URLs (as defined in the assignment specifications)
WEBPAGE_URLS = {
    "top-gainers-losers": f"{NSE_BASE_URL}/market-data/top-gainers-losers",
    "upper-band-hitters": f"{NSE_BASE_URL}/market-data/upper-band-hitters",
    "volume-gainers-spurts": f"{NSE_BASE_URL}/market-data/volume-gainers-spurts",
    "52-week-high-equity": f"{NSE_BASE_URL}/market-data/52-week-high-equity-market",
}

# API Data Endpoints used by the respective NSE webpages
API_ENDPOINTS = {
    "top-gainers": f"{NSE_BASE_URL}/api/live-analysis-variations?index=gainers",
    "top-losers": f"{NSE_BASE_URL}/api/live-analysis-variations?index=loosers",
    "upper-band-hitters": f"{NSE_BASE_URL}/api/live-analysis-price-band-hitter",
    "volume-gainers-spurts": f"{NSE_BASE_URL}/api/live-analysis-volume-gainers",
    "52-week-high-equity": f"{NSE_BASE_URL}/api/live-analysis-data-52weekhighstock",
}

# HTTP Request Headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

# Network and Resilience Configuration
REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.5  # exponential backoff delay multiplier

# Dataset Metadata and Schema Specifications
DATASETS = {
    "top-gainers-losers": {
        "display_name": "Top Gainers / Losers",
        "file_prefix": "top_gainers_losers",
        "webpage_url": WEBPAGE_URLS["top-gainers-losers"],
        "required_columns": [
            "symbol",
            "series",
            "ltp",
            "perChange",
            "variation_type",
        ],
        "key_columns": ["symbol", "series", "variation_type"],
    },
    "upper-band-hitters": {
        "display_name": "Upper Band Hitters",
        "file_prefix": "upper_band_hitters",
        "webpage_url": WEBPAGE_URLS["upper-band-hitters"],
        "required_columns": [
            "symbol",
            "series",
            "ltp",
            "change",
            "pChange",
            "priceBand",
        ],
        "key_columns": ["symbol", "series"],
    },
    "volume-gainers-spurts": {
        "display_name": "Volume Gainers / Spurts",
        "file_prefix": "volume_gainers_spurts",
        "webpage_url": WEBPAGE_URLS["volume-gainers-spurts"],
        "required_columns": [
            "symbol",
            "companyName",
            "volume",
            "ltp",
            "pChange",
        ],
        "key_columns": ["symbol"],
    },
    "52-week-high-equity": {
        "display_name": "52-Week High – Equity Market",
        "file_prefix": "52_week_high_equity",
        "webpage_url": WEBPAGE_URLS["52-week-high-equity"],
        "required_columns": [
            "symbol",
            "series",
            "ltp",
            "pChange",
            "new52WHL",
        ],
        "key_columns": ["symbol", "series"],
    },
}

SUPPORTED_DATASET_KEYS = list(DATASETS.keys())
