import os
import threading
import pickle
import time
from typing import Dict, Any
import yfinance as yf
import pandas as pd

# Directory for persistent cache
data_cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'cache')
os.makedirs(data_cache_dir, exist_ok=True)

# Lock for thread-safe cache access
cache_lock = threading.Lock()

# Cache expiration in seconds (e.g., 12 hours)
CACHE_TTL = 12 * 3600

# Helper: cache file path for a ticker and data type
def _cache_path(ticker: str, data_type: str) -> str:
    safe_ticker = ticker.replace('/', '_').replace(':', '_')
    return os.path.join(data_cache_dir, f"{safe_ticker}_{data_type}.pkl")

# Helper: load from cache if not expired
def _load_cache(ticker: str, data_type: str):
    path = _cache_path(ticker, data_type)
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        data, ts = pickle.load(f)
    if time.time() - ts > CACHE_TTL:
        return None
    return data

# Helper: save to cache
def _save_cache(ticker: str, data_type: str, data):
    path = _cache_path(ticker, data_type)
    with open(path, 'wb') as f:
        pickle.dump((data, time.time()), f)

# Centralized fetcher class
class DataFetcher:
    def __init__(self):
        self.memory_cache: Dict[str, Dict[str, Any]] = {}

    def get_all(self, ticker: str) -> Dict[str, Any]:
        """
        Fetches all required data for a ticker in parallel (info, financials, history, etc).
        Returns a dict with all data.
        """
        results = {}
        threads = []
        data_types = ['info', 'financials', 'balance_sheet', 'cashflow', 'earnings', 'history']

        def fetch_and_store(data_type):
            data = self.get_data(ticker, data_type)
            with cache_lock:
                results[data_type] = data

        for dt in data_types:
            t = threading.Thread(target=fetch_and_store, args=(dt,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        return results

def get_data(self, ticker: str, data_type: str):
    key = f"{ticker}_{data_type}"

    # 1. Check in-memory cache
    if key in self.memory_cache:
        return self.memory_cache[key]

    # 2. Check persistent cache
    with cache_lock:
        cached = _load_cache(ticker, data_type)
    if cached is not None:
        self.memory_cache[key] = cached
        return cached

    # 3. Fetch from yfinance
    yf_ticker = yf.Ticker(ticker)
    data = None

    try:
        if data_type == 'info':
            data = yf_ticker.info
        elif data_type == 'financials':
            data = yf_ticker.financials.to_dict()
        elif data_type == 'balance_sheet':
            data = yf_ticker.balance_sheet.to_dict()
        elif data_type == 'cashflow':
            data = yf_ticker.cashflow.to_dict()
        elif data_type == 'earnings':
            # Replace deprecated 'earnings' with income_stmt fallback
            income_stmt = yf_ticker.income_stmt
            if isinstance(income_stmt, pd.DataFrame) and "Net Income" in income_stmt.index:
                data = income_stmt.loc["Net Income"].to_dict()
            else:
                data = {}
        elif data_type == 'history':
            hist_df = yf_ticker.history(period='max')
            data = hist_df.to_dict() if isinstance(hist_df, pd.DataFrame) else {}
    except Exception as e:
        data = {}

    # 4. Save to caches
    self.memory_cache[key] = data
    with cache_lock:
        _save_cache(ticker, data_type, data)

    return data


# Singleton instance for app-wide use
data_fetcher = DataFetcher()

def get_ticker_data(ticker: str) -> Dict[str, Any]:
    """
    Public API: Fetch all data for a ticker (info, financials, etc) in parallel, using persistent cache.
    """
    return data_fetcher.get_all(ticker)

