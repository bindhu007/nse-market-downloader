-- Database Schema for NSE Market Data Downloader
-- Compatible with SQLite, PostgreSQL, and MySQL

-- 1. Top Gainers and Losers
CREATE TABLE IF NOT EXISTS top_gainers_losers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL,
    series VARCHAR(10),
    open_price REAL,
    high_price REAL,
    low_price REAL,
    ltp REAL NOT NULL,
    nearWKH REAL,
    nearWKL REAL,
    prev_price REAL,
    net_price REAL,
    trade_quantity VARCHAR(30),
    turnover VARCHAR(30),
    market_type VARCHAR(10),
    ca_ex_dt VARCHAR(30),
    ca_purpose TEXT,
    perChange REAL NOT NULL,
    variation_type VARCHAR(10) NOT NULL, -- 'GAINER' or 'LOSER'
    trading_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, series, variation_type, trading_date)
);

-- 2. Upper Band Hitters
CREATE TABLE IF NOT EXISTS upper_band_hitters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL,
    series VARCHAR(10),
    nearWKH REAL,
    nearWKL REAL,
    ltp REAL NOT NULL,
    change REAL,
    pChange REAL,
    priceBand VARCHAR(20),
    highPrice REAL,
    lowPrice REAL,
    yearHigh REAL,
    yearLow REAL,
    totalTradedVol VARCHAR(30),
    turnover VARCHAR(30),
    totalTradedVolcsv BIGINT,
    turnovercsv REAL,
    trading_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, series, trading_date)
);

-- 3. Volume Gainers and Spurts
CREATE TABLE IF NOT EXISTS volume_gainers_spurts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL,
    companyName VARCHAR(255),
    volume VARCHAR(30),
    week1AvgVolume BIGINT,
    week1volChange REAL,
    week2AvgVolume BIGINT,
    week2volChange REAL,
    ltp REAL NOT NULL,
    pChange REAL,
    turnover VARCHAR(30),
    trading_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, trading_date)
);

-- 4. 52-Week High Equity Market
CREATE TABLE IF NOT EXISTS fifty_two_week_high_equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(30) NOT NULL,
    series VARCHAR(10),
    companyName VARCHAR(255),
    ltp REAL NOT NULL,
    change REAL,
    pChange REAL,
    prevClose REAL,
    new52WHL REAL,
    prev52WHL REAL,
    prevHLDate VARCHAR(30),
    nearWKH REAL,
    nearWKL REAL,
    trading_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, series, trading_date)
);

-- Indexes for performance on symbol and date queries
CREATE INDEX IF NOT EXISTS idx_gainers_symbol_date ON top_gainers_losers(symbol, trading_date);
CREATE INDEX IF NOT EXISTS idx_band_symbol_date ON upper_band_hitters(symbol, trading_date);
CREATE INDEX IF NOT EXISTS idx_vol_symbol_date ON volume_gainers_spurts(symbol, trading_date);
CREATE INDEX IF NOT EXISTS idx_52w_symbol_date ON fifty_two_week_high_equity(symbol, trading_date);
