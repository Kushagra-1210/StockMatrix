# backend/data_provider.py
import pandas as pd
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
        self._data = get_ticker_data(ticker)
        
        if "error" in self._data:
            raise ValueError(f"Failed to fetch initial data for {ticker}: {self._data['error']}")

    def get_info(self) -> dict:
        """Provides the general company information dictionary."""
        return self._data.get("info", {})

    def get_financial_statements(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Provides clean, ready-to-use financial statement DataFrames."""
        financials = pd.DataFrame(self._data['financials']['data'], columns=self._data['financials']['columns'], index=self._data['financials']['index']) if self._data.get("financials") else pd.DataFrame()
        balance_sheet = pd.DataFrame(self._data['balance_sheet']['data'], columns=self._data['balance_sheet']['columns'], index=self._data['balance_sheet']['index']) if self._data.get("balance_sheet") else pd.DataFrame()
        cashflow = pd.DataFrame(self._data['cashflow']['data'], columns=self._data['cashflow']['columns'], index=self._data['cashflow']['index']) if self._data.get("cashflow") else pd.DataFrame()
        return financials, balance_sheet, cashflow

    def get_fmp_data(self) -> dict:
        """Provides the raw fallback data dictionary from FMP."""
        return self._data.get("fmp_data", {})

    def get_history(self) -> pd.DataFrame:
        """
        Provides sanitized and standardized historical price data.
        - Drops any rows with missing OHLC data to ensure calculation accuracy.
        - For stocks with >2 years of history, it returns the last 2 years.
        - For stocks with <2 years of history, it returns the maximum available data.
        """
        history_dict = self._data.get("history", {})
        if not history_dict:
            return pd.DataFrame()
        
        df = pd.DataFrame(history_dict)
        
        # --- DATA SANITIZATION (CRITICAL FIX) ---
        # Ensure essential columns exist and drop any row with missing price data.
        ohlc_cols = ['Open', 'High', 'Low', 'Close']
        if not all(col in df.columns for col in ohlc_cols):
            return pd.DataFrame() # Return empty if data is malformed
        df.dropna(subset=ohlc_cols, inplace=True)

        df['Date'] = pd.to_datetime(df['Date'])
        
        # Ensure the 'Date' column is timezone-naive.
        if df['Date'].dt.tz is not None:
            df['Date'] = df['Date'].dt.tz_localize(None)
        
        # --- STANDARDIZE LOOKBACK PERIOD (CRITICAL FIX) ---
        two_years_ago = pd.Timestamp.now().tz_localize(None) - pd.DateOffset(years=2)
        
        if not df.empty and df['Date'].iloc[0] < two_years_ago:
            df = df[df['Date'] >= two_years_ago]
        
        return df

