# Project Engineering Notes & Architecture Decisions

**Project:** NSE Market Data Downloader  
**Author:** Bindhu Mallikarjuna  
**Repository:** [https://github.com/bindhu007/nse-market-downloader](https://github.com/bindhu007/nse-market-downloader)  

---

## 1. Architectural Decisions & Engineering Trade-offs

### 1.1 Programmatic HTTP Access vs. Headless Browsers
- **Decision:** Used `requests.Session` with initial session handshake and standard browser headers rather than browser automation frameworks like Selenium or Playwright.
- **Rationale:** 
  - **Speed & Resource Efficiency:** The full pipeline completes in **~1.2 seconds** compared to 15–30 seconds required by a headless browser spin-up.
  - **Compliance:** Aligns with the assignment's core guideline to use permitted data-access methods without heavy scraping or attempting to bypass protections.
  - **Reliability:** Headless browsers introduce heavy dependencies, brittle DOM selectors, and rendering latency. Replicating the web client's session state provides clean, structured JSON payloads directly.

### 1.2 Strict Separation of Concerns (Single Responsibility Principle)
The project is strictly decomposed into 6 distinct modules:
1. `config.py`: Single source of truth for endpoints, headers, schema definitions, and retry parameters. Prevents hardcoded magic numbers or URLs.
2. `fetcher.py`: Manages network state, cookies, retries, and HTTP error translation.
3. `validator.py`: Pure data validation and sanitization. Operates on raw data dictionaries without any knowledge of network or disk.
4. `storage.py`: Persistence abstraction. Handles atomic file writes, canonical trading-date filenames, and optional database sinks.
5. `logger.py`: Centralized multi-sink logging (stdout + rotating daily file log).
6. `main.py`: Command-line interface and workflow orchestrator.

**Maintainability Impact:** If NSE alters an API path or adds query parameters, only `config.py` or `fetcher.py` is modified. The validation, storage, and execution logic remain untouched.

### 1.3 Fault Isolation and Resilient Execution
- **Decision:** Each dataset is fetched, validated, and saved in an independent `try...except` block within `run_pipeline()`.
- **Rationale:** Network blips, unexpected server 500s, or missing endpoints on a single dataset should **never abort the entire collection run**.
- **Result:** If dataset 3 fails, datasets 1, 2, and 4 are still saved, the failure is logged with a full stack trace to disk, and a summary report is printed at the end highlighting the exact success/failure status.

### 1.4 Idempotent & Atomic File Persistence
- **Decision:** Writes data to a temporary file (`tempfile.NamedTemporaryFile`) within the destination directory first, followed by an atomic rename using `os.replace`.
- **Rationale:**
  - Prevents corrupted or partial CSV files if the process is killed midway (e.g., SIGINT, power loss).
  - Safely handles multiple executions on the same trading day by refreshing the authoritative `{dataset}_{date}.csv` without creating cluttered duplicates like `file(1).csv`.

---

## 2. NSE Endpoint Discovery & Data Nuances

During the inspection of the four target NSE webpages, the following technical details were identified:

1. **Top Gainers / Losers (`/market-data/top-gainers-losers`)**:
   - The frontend calls `/api/live-analysis-variations?index=gainers` and `/api/live-analysis-variations?index=loosers` (note the historical double 'o' spelling in the NSE parameter).
   - Each response contains sector variations (`allSec`, `NIFTY`, `BANKNIFTY`). The fetcher extracts `allSec` (with fallback to `NIFTY`), adds a `variation_type` tag (`GAINER` / `LOSER`), and merges them.

2. **Upper Band Hitters (`/market-data/upper-band-hitters`)**:
   - The webpage script `upper-band-hitters.js` queries `/api/live-analysis-price-band-hitter`.
   - The payload contains `upper`, `lower`, `both`, and `count`. The `upper['AllSec']['data']` list contains the stocks that reached the maximum allowable upper circuit limit for the session.

3. **Volume Gainers / Spurts (`/market-data/volume-gainers-spurts`)**:
   - The frontend queries `/api/live-analysis-volume-gainers`.
   - Returns stocks experiencing sudden trading volume jumps, including 1-week and 2-week average volume comparisons (`week1AvgVolume`, `week1volChange`).

4. **52-Week High – Equity Market (`/market-data/52-week-high-equity-market`)**:
   - Handled via `52week-high.js` calling `/api/live-analysis-data-52weekhighstock`.
   - Contains historical benchmark fields: `new52WHL`, `prev52WHL`, and `prevHLDate`.
   - Note on typo handling: NSE occasionally serializes `companyName` as `comapnyName` in this endpoint; the validator normalizes this alias automatically.

---

## 3. Interview Questions & Technical Answers

### Q1: What is the difference between Top Gainers and Volume Gainers?
- **Top Gainers** are stocks with the highest percentage price increase (`pChange` or `net_price`) compared to their previous closing price.
- **Volume Gainers** are stocks experiencing unusually high trading volume compared to their historical averages (e.g., 1-week or 2-week average volume), regardless of whether their price increased or decreased.

### Q2: What is an Upper Band Hitter (Upper Circuit)?
- Indian stock exchanges enforce daily price movement bands (typically 5%, 10%, or 20%) to curb extreme volatility and manipulation.
- When a stock rises to the ceiling of its permitted band, trading in that stock is restricted to that upper price limit (no seller exists at higher prices), and it is classified as an **Upper Band Hitter**.

### Q3: Why did you use Pandas for this assignment?
- Pandas provides an industry-standard, high-performance data abstraction (`DataFrame`) for tabular manipulation.
- It enables vectorized schema checks, string whitespace normalization, composite deduplication (`df.drop_duplicates`), and reliable CSV serialization with standard quote and comma handling.

### Q4: How does your application prevent duplicate records?
- In `validator.py`, each dataset defines key identifying columns (e.g., `['symbol', 'series']` or `['symbol']`).
- Before writing, `df.duplicated(subset=key_cols)` detects repeated rows, logs the exact number of duplicates removed, and retains the first unique occurrence.

### Q5: How do you handle network and server failures?
- `fetcher.py` uses an exponential backoff retry loop with randomized jitter: `delay = (backoff_factor ** attempt) + random_jitter`.
- Transient network drops and HTTP 5xx errors are retried up to 3 times. Client errors like HTTP 404 fail fast without wasting retries.
- If HTTP 401/403 occurs due to an expired session cookie, the fetcher triggers a session re-handshake and retries the request.

### Q6: How do you test the downloader without hitting live NSE servers repeatedly?
- In `tests/`, all 35 tests use `unittest.mock` to mock `requests.Session`.
- This enables comprehensive, instantaneous unit testing of edge cases (e.g., 404 errors, 500 server crashes, DNS timeouts, malformed JSON, missing columns, and empty datasets) in under 2.5 seconds without internet access.

---

## 4. Verification and Benchmark Statistics

- **Live Run Record Counts (Trading Day: 2026-11-11):**
  - Top Gainers / Losers: **40 records**
  - Upper Band Hitters: **151 records**
  - Volume Gainers / Spurts: **25 records**
  - 52-Week High – Equity: **106 records**
  - **Total:** **322 live records**
- **Live Pipeline Execution Time:** **~1.23 seconds**
- **Test Suite Execution Time:** **35 passed in 2.31 seconds**
