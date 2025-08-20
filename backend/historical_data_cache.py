# backend/historical_data_cache.py
import pandas as pd
import yfinance as yf
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

CACHE_DIR = "historical_cache"

class HistoricalDataCache:
    """
    Manages fetching and caching of historical stock data to avoid repeated downloads.
    """
    def __init__(self, tickers: list, start_date: str, end_date: str):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.price_data = {} # Will store DataFrames {ticker: df}
        
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
            logger.info(f"Created cache directory at {CACHE_DIR}")

    def _get_cache_path(self, ticker: str):
        """Generates the file path for a given ticker's cache file."""
        safe_ticker = ticker.replace("^", "INDEX_") # Sanitize benchmark tickers for filenames
        return os.path.join(CACHE_DIR, f"{safe_ticker}_prices.parquet")

    def load_all_data(self):
        """
        Loads all required historical price data, fetching from API if not in cache.
        """
        logger.info("Loading historical data from cache/API...")
        for ticker in self.tickers:
            cache_path = self._get_cache_path(ticker)
            try:
                if os.path.exists(cache_path):
                    # Load from cache if it exists
                    df = pd.read_parquet(cache_path)
                    self.price_data[ticker] = df['Close']
                    logger.debug(f"Loaded {ticker} from cache.")
                else:
                    # Fetch from yfinance if not cached
                    df = yf.download(ticker, start=self.start_date, end=self.end_date, progress=False)
                    if not df.empty:
                        df.to_parquet(cache_path)
                        self.price_data[ticker] = df['Close']
                        logger.info(f"Fetched and cached {ticker} from yfinance.")
                    else:
                        logger.warning(f"No data returned for {ticker} from yfinance.")
                        self.price_data[ticker] = None
            except Exception as e:
                logger.error(f"Failed to load/fetch data for {ticker}: {e}")
                self.price_data[ticker] = None
        logger.info("Finished loading all historical data.")

    def get_price_data(self, ticker: str) -> pd.Series | None:
        """
        Returns the historical closing price Series for a given ticker.
        """
        return self.price_data.get(ticker)

# Note: A true point-in-time backtester would also cache fundamental data
# on a quarterly basis. This implementation simplifies by caching prices only.
