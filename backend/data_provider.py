# backend/data_provider.py
import pandas as pd
from datetime import datetime, timedelta
from backend.data_fetcher import get_ticker_data

class DataProvider:
    """
    A data abstraction layer that provides a clean, consistent interface 
    for accessing stock data. It handles fetching, caching, sanitizing, 
    and standardizing the lookback period of the data.
    """
    def __init__(self, ticker: str):
        """
        Initializes the DataProvider for a specific ticker.

        Args:
            ticker (str): The stock ticker symbol.

        Raises:
            ValueError: If the initial data fetch fails and returns an error.
        """
        self.ticker = ticker
        # Fetch data using a specific period to ensure consistency
        self._data = get_ticker_data(ticker) 
        
        if "error" in self._data:
            raise ValueError(f"Failed to fetch initial data for {ticker}: {self._data['error']}")

    def get_info(self) -> dict:
        """Provides the general company information dictionary."""
        return self._data.get("info", {})

    def get_financial_statements(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Provides clean, ready-to-use financial statement DataFrames."""
        financials = pd.DataFrame(self._data['financials']['data'], columns=self._data['financials']['columns'], index=self._data['financials']['index']) if self._data.get("financials") and self._data['financials'].get('data') else pd.DataFrame()
        balance_sheet = pd.DataFrame(self._data['balance_sheet']['data'], columns=self._data['balance_sheet']['columns'], index=self._data['balance_sheet']['index']) if self._data.get("balance_sheet") and self._data['balance_sheet'].get('data') else pd.DataFrame()
        cashflow = pd.DataFrame(self._data['cashflow']['data'], columns=self._data['cashflow']['columns'], index=self._data['cashflow']['index']) if self._data.get("cashflow") and self._data['cashflow'].get('data') else pd.DataFrame()
        return financials, balance_sheet, cashflow

    def get_fmp_data(self) -> dict:
        """Provides the raw fallback data dictionary from FMP."""
        return self._data.get("fmp_data", {})

    def get_history(self) -> pd.DataFrame:
        """
        Provides sanitized and standardized historical price data.
        - Fetches a 2.5-year window to ensure accurate 200-day SMA.
        - Drops any rows with missing OHLC data or zero volume.
        - Sorts data chronologically.
        """
        history_dict = self._data.get("history", {})
        if not history_dict:
            return pd.DataFrame()
        
        df = pd.DataFrame(history_dict)
        
        # --- DATA SANITIZATION (CRITICAL FIX) ---
        ohlc_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in ohlc_cols):
            return pd.DataFrame()
        
        # 1. Drop rows with any missing price/volume data
        df.dropna(subset=ohlc_cols, inplace=True)
        
        # 2. Convert to numeric, coercing errors, and drop if conversion fails
        for col in ohlc_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=ohlc_cols, inplace=True)

        # 3. Remove rows with zero volume, as they are not valid trading days
        df = df[df['Volume'] > 0]

        if df.empty:
            return pd.DataFrame()

        # 4. Handle dates and sort
        df['Date'] = pd.to_datetime(df['Date'])
        if df['Date'].dt.tz is not None:
            df['Date'] = df['Date'].dt.tz_localize(None)
        
        df.sort_values(by='Date', inplace=True)
        
        # --- STANDARDIZE LOOKBACK PERIOD ---
        two_years_ago = datetime.now() - timedelta(days=730)
        df = df[df['Date'] >= two_years_ago]
        
        return df
