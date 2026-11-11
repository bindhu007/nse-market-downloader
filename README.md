# NSE Market Data Downloader

An automated, reliable Python backend data collection pipeline that retrieves market data from four National Stock Exchange of India (NSE) webpages and persists the validated information into four independent CSV files.

Designed and engineered following production-quality Python design patterns, strict separation of concerns, defensive validation, error isolation, and resilient session management.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Target Datasets](#target-datasets)
3. [Architecture and Design](#architecture-and-design)
4. [Technology Stack](#technology-stack)
5. [Project Structure](#project-structure)
6. [Installation and Environment Setup](#installation-and-environment-setup)
7. [Command-Line Interface (CLI) Usage](#command-line-interface-cli-usage)
8. [Data Acquisition and Session Management](#data-acquisition-and-session-management)
9. [Data Validation and Quality Assurance](#data-validation-and-quality-assurance)
10. [Storage and Duplicate File Management](#storage-and-duplicate-file-management)
11. [Logging and Error Handling](#logging-and-error-handling)
12. [Automated Testing](#automated-testing)
13. [Database Schema (Bonus Feature)](#database-schema-bonus-feature)
14. [Docker Deployment](#docker-deployment)
15. [Limitations and Assumptions](#limitations-and-assumptions)

---

## 1. Project Overview

The **NSE Market Data Downloader** is a command-line tool built to address the requirements of the NSE Data Engineering Internship Assignment. It automates the retrieval of daily market activity across four major NSE market indicator pages:

1. **Top Gainers / Losers**
2. **Upper Band Hitters**
3. **Volume Gainers / Spurts**
4. **52-Week High – Equity Market**

### Core Architectural Principles

- **No Manual Intervention**: Automated programmatic extraction.
- **Fault Isolation**: Failure in retrieving one dataset **never** halts the retrieval of the remaining datasets.
- **Schema Validation**: Datasets are checked against strict schema definitions; empty responses, missing columns, or malformed data are rejected.
- **Idempotent File Management**: Repeated executions for the same trading day update the day's authoritative CSV cleanly via atomic replacement without creating confusing duplicate filenames.
- **Permitted Access**: Respects NSE's access mechanisms by executing the standard session handshake (obtaining session cookies) and requesting official API endpoints utilized by NSE's frontend application.

---

## 2. Target Datasets

| Dataset | NSE Webpage URL | Underlying API Endpoint | Output Filename Format |
|---|---|---|---|
| **Top Gainers / Losers** | `/market-data/top-gainers-losers` | `/api/live-analysis-variations?index=gainers` & `index=loosers` | `top_gainers_losers_YYYY-MM-DD.csv` |
| **Upper Band Hitters** | `/market-data/upper-band-hitters` | `/api/live-analysis-price-band-hitter` | `upper_band_hitters_YYYY-MM-DD.csv` |
| **Volume Gainers / Spurts** | `/market-data/volume-gainers-spurts` | `/api/live-analysis-volume-gainers` | `volume_gainers_spurts_YYYY-MM-DD.csv` |
| **52-Week High** | `/market-data/52-week-high-equity-market` | `/api/live-analysis-data-52weekhighstock` | `52_week_high_equity_YYYY-MM-DD.csv` |

---

## 3. Architecture and Design

The application follows a modular, decoupled architecture:

```
┌────────────────────────────────────────────────────────┐
│                        main.py                         │
│             (CLI & Pipeline Orchestrator)              │
└────────────┬───────────────┬──────────────┬────────────┘
             │               │              │
             ▼               ▼              ▼
     ┌──────────────┐ ┌─────────────┐ ┌────────────┐
     │  fetcher.py  │ │validator.py │ │ storage.py │
     │ (Acquisition)│ │(Validation) │ │(Persistence│
     └───────┬──────┘ └──────┬──────┘ └─────┬──────┘
             │               │              │
             └───────────────┼──────────────┘
                             ▼
                    ┌─────────────────┐
                    │    logger.py    │
                    │   & config.py   │
                    └─────────────────┘
```

### Module Responsibilities

1. **`config.py`**: Centralizes URLs, request headers, timeouts, retry parameters, and dataset schema requirements. Eliminates hardcoded magic strings.
2. **`fetcher.py`**: Encapsulates `requests.Session` handling, browser handshake cookie initialization, exponential backoff retries, and dataset-specific parsing.
3. **`validator.py`**: Validates non-empty datasets, required columns, deduplication, and whitespace normalization while preserving original price and volume values.
4. **`storage.py`**: Safely writes validated DataFrames to CSV files using atomic file swaps, preventing file corruption if interrupted. Supports SQLite persistence (`--db`).
5. **`logger.py`**: Configures unified logging to standard output and rotating daily log files in `logs/`.
6. **`main.py`**: Parses CLI arguments, iterates through selected datasets with fault tolerance, logs operations, and prints a final execution summary table.

---

## 4. Technology Stack

- **Python 3.9+ / 3.13**: Core programming language.
- **Requests**: HTTP client for interacting with NSE endpoints.
- **Pandas**: Tabular data structuring, deduplication, and CSV generation.
- **BeautifulSoup4**: HTML parsing and inspection utilities.
- **Argparse**: Standard library command-line parser.
- **Pytest**: Automated testing framework with mocks.
- **SQLite3**: Embedded relational database for structured bonus persistence.

---

## 5. Project Structure

```
nse-market-downloader/
│
├── config.py                 # Central configuration, URLs, headers, schemas
├── fetcher.py                # Data acquisition with session & retry logic
├── validator.py              # Data cleaning, column checks, deduplication
├── storage.py                # CSV atomic file writer and SQLite persistence
├── logger.py                 # Multi-sink logging configuration
├── main.py                   # Main CLI entry point and pipeline orchestrator
│
├── requirements.txt          # Python dependencies
├── pytest.ini                # Pytest path and runner configuration
├── schema.sql                # SQL database schema definition
├── Dockerfile                # Container build specification
├── docker-compose.yml        # Multi-container orchestration
├── README.md                 # Complete system documentation
├── .gitignore                # Ignored files (venv, logs, pycache)
│
├── tests/                    # Automated Pytest suite
│   ├── test_fetcher.py       # Unit tests for HTTP fetcher & retries
│   ├── test_validator.py     # Unit tests for schema validation & deduplication
│   ├── test_storage.py       # Unit tests for CSV writing & atomic file ops
│   └── test_main.py          # Integration tests for CLI & fault isolation
│
├── output/                   # Generated output CSV files
│   ├── top_gainers_losers_2026-11-11.csv
│   ├── upper_band_hitters_2026-11-11.csv
│   ├── volume_gainers_spurts_2026-11-11.csv
│   ├── 52_week_high_equity_2026-11-11.csv
│   └── nse_market_data.db    # Optional SQLite database (with --db)
│
└── logs/                     # Application execution logs
    └── nse_downloader_2026-11-11.log
```

---

## 6. Installation and Environment Setup

### Step 1: Clone or Navigate to Project Directory

```bash
cd nse-market-downloader
```

### Step 2: Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Required Dependencies

```bash
pip install -r requirements.txt
```

Verify installation:

```bash
python -c "import requests, pandas, bs4, pytest; print('Environment ready!')"
```

---

## 7. Command-Line Interface (CLI) Usage

### 1. Download All Four Datasets (Default)

```bash
python main.py
```

*Attempts to download, validate, and save all 4 datasets.*

### 2. Download Individual Datasets

#### Top Gainers / Losers:
```bash
python main.py --dataset top-gainers-losers
```

#### Upper Band Hitters:
```bash
python main.py --dataset upper-band-hitters
```

#### Volume Gainers / Spurts:
```bash
python main.py --dataset volume-gainers-spurts
```

#### 52-Week High – Equity Market:
```bash
python main.py --dataset 52-week-high-equity
```

### 3. Advanced Options

- **Specify Custom Output Directory**:
  ```bash
  python main.py --output-dir /path/to/custom_dir
  ```

- **Persist to SQLite in addition to CSV (Bonus Feature)**:
  ```bash
  python main.py --db
  ```

- **Specify Custom Trading Date Override**:
  ```bash
  python main.py --date 2026-11-11
  ```

---

## 8. Data Acquisition and Session Management

NSE India utilizes security layers that require clients to establish session cookies before requesting JSON data endpoints.

### Acquisition Lifecycle in `fetcher.py`:

1. **Initial Handshake**: The fetcher visits the target market-data webpage using standard browser headers (`User-Agent`, `Accept`, `Accept-Language`, `Connection`).
2. **Cookie Acquisition**: The server sets session cookies (`nsit`, `AKA_A2`, `_abck`, `bm_sz`).
3. **Endpoint Request**: The fetcher queries the corresponding JSON API with the established cookies and an explicit `Referer` header matching the source webpage.
4. **Automatic Re-handshake**: If an HTTP 401 or 403 response is detected (indicating an expired session cookie), the fetcher automatically re-initializes the session and retries the request.
5. **Exponential Backoff**: Transient network errors (timeouts, connection drops) are retried up to 3 times with exponential backoff and jitter (`delay = backoff_factor ^ attempt + random_jitter`).

---

## 9. Data Validation and Quality Assurance

Before any dataset is written to disk, it passes through `validator.py`:

1. **Structure Verification**: Ensures the payload is a valid list of dictionaries.
2. **Non-Empty Guarantee**: Rejects empty payloads (`None` or `[]`) by raising `EmptyDataError`.
3. **Required Columns Check**: Verifies essential columns exist (e.g. `symbol`, `ltp`, `series`). Raises `MissingColumnsError` if any are missing.
4. **Column Alias Normalization**: Maps known NSE typographical variations (e.g., `comapnyName` -> `companyName`).
5. **Whitespace Trimming**: Cleans leading and trailing whitespace from string columns without modifying actual numerical or market values.
6. **Deduplication**: Identifies duplicate stock records based on key columns (`symbol`, `series`), logs the count of removed duplicates, and retains the first occurrence.
7. **Trading Date Integrity**: Appends the trading date as a first-class column for historical record keeping.

---

## 10. Storage and Duplicate File Management

Persisted files are managed by `storage.py`:

### Canonical Filename Pattern

`{prefix}_{trading_date}.csv`

Examples:
- `output/top_gainers_losers_2026-11-11.csv`
- `output/upper_band_hitters_2026-11-11.csv`
- `output/volume_gainers_spurts_2026-11-11.csv`
- `output/52_week_high_equity_2026-11-11.csv`

### Safe Same-Day Re-runs

If the downloader is run multiple times on the same trading day:
- **Atomic File Swaps**: The application writes new records to a temporary file in the destination folder first, then atomically replaces the existing file (`os.replace`).
- **No Incomplete Files**: A crash or network abort never leaves a half-written or corrupt CSV.
- **No Cluttered Filenames**: Avoids creating confusing files like `file(1).csv`, `file_copy.csv`.

---

## 11. Logging and Error Handling

### Logging Destinations

1. **Console (stdout)**: Real-time progress and summary table.
2. **File sink (`logs/nse_downloader_YYYY-MM-DD.log`)**: Full historical record with timestamps and error tracebacks.

### Fault Isolation Guarantee

When executing `python main.py` across all datasets, each dataset is wrapped in an independent try-except block:

```
Dataset 1: Top Gainers / Losers     ──> SUCCESS ──> CSV Saved
Dataset 2: Upper Band Hitters       ──> SUCCESS ──> CSV Saved
Dataset 3: Volume Gainers / Spurts  ──> FAILED  ──> Log Error & Continue
Dataset 4: 52-Week High             ──> SUCCESS ──> CSV Saved

Final Summary: 3 Succeeded, 1 Failed
```

---

## 12. Automated Testing

The project includes a comprehensive unit and integration test suite using **Pytest** with 100% mocked external dependencies.

### Running Tests

```bash
pytest -v
```

### Verified Test Cases (35 Passed Tests)

- **`test_fetcher.py`**:
  - NSE timestamp parsing into ISO dates (`YYYY-MM-DD`).
  - Session cookie initialization.
  - Successful JSON response decoding.
  - HTTP 404 client error handling (no retries).
  - HTTP 500 server error handling with retry verification.
  - Network timeouts and connection drops.
  - Malformed JSON handling (`NSEDataFormatError`).
  - Dataset-specific fetchers for all 4 datasets.
  - Unknown dataset key rejection.

- **`test_validator.py`**:
  - Successful validation for valid records.
  - Rejection of empty records (`EmptyDataError`).
  - Rejection of invalid non-list/non-dict data formats.
  - Missing column detection (`MissingColumnsError`).
  - Duplicate record detection and dropping.
  - Whitespace trimming on text fields.
  - Typo column normalization (`comapnyName` -> `companyName`).
  - Market value integrity preservation.

- **`test_storage.py`**:
  - Canonical filename generation.
  - CSV file creation and column verification.
  - Repeated execution on the same trading day (atomic replace).
  - Deep nested output directory creation.
  - Disk write permission error handling (`StorageError`).
  - SQLite database storage and query verification.

- **`test_main.py`**:
  - CLI argument parsing (default and custom flags).
  - Downloading all four datasets simultaneously.
  - Downloading a single selected dataset.
  - Fault tolerance: failure in one dataset continues remaining downloads.

---

## 13. Database Schema (Bonus Feature)

When running with `--db`, data is simultaneously written to an SQLite database (`output/nse_market_data.db`).

The corresponding production SQL schema is provided in [`schema.sql`](file:///Users/bindhumallikarjuna/.gemini/antigravity/scratch/nse-market-downloader/schema.sql) with definitions for:
- `top_gainers_losers`
- `upper_band_hitters`
- `volume_gainers_spurts`
- `fifty_two_week_high_equity`

---

## 14. Docker Deployment

### Build the Image:

```bash
docker build -t nse-downloader .
```

### Run the Container:

```bash
docker run --rm -v $(pwd)/output:/app/output -v $(pwd)/logs:/app/logs nse-downloader
```

### Run with Docker Compose:

```bash
docker-compose up --build
```

---

## 15. Limitations and Assumptions

1. **Market Hours & Trading Days**: NSE updates intraday variation figures between 09:15 and 15:30 IST on trading days (Monday through Friday). On weekends or market holidays, the pages display the last recorded trading day's closing values.
2. **Access Policy**: The tool queries NSE India endpoints using standard browser headers and session cookies. It does not employ headless browser automation or bypass access controls.
3. **Network Availability**: Outbound internet connectivity to `nseindia.com` is required for live data retrieval.
